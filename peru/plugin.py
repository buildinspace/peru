from collections import namedtuple
import contextlib
import os
import subprocess
import sys
import tempfile

import yaml

from .async_helpers import create_subprocess_with_handle
from .async_exit_stack import AsyncExitStack
from . import cache
from . import compat
from .compat import makedirs
from .error import PrintableError

DEFAULT_PARALLEL_FETCH_LIMIT = 10

DEBUG_PARALLEL_COUNT = 0
DEBUG_PARALLEL_MAX = 0

PluginDefinition = namedtuple('PluginDefinition', [
    'type', 'sync_exe', 'reup_exe', 'fields', 'required_fields',
    'optional_fields', 'cache_fields'
])

PluginContext = namedtuple('PluginContext', [
    'cwd', 'plugin_cache_root', 'parallelism_semaphore', 'plugin_cache_locks',
    'tmp_root'
])


async def plugin_fetch(plugin_context, module_type, module_fields, dest,
                       display_handle):
    env = {'PERU_SYNC_DEST': dest}
    await _plugin_job(plugin_context, module_type, module_fields, 'sync', env,
                      display_handle)


async def plugin_get_reup_fields(plugin_context, module_type, module_fields,
                                 display_handle):
    with tmp_dir(plugin_context) as output_file_dir:
        output_path = os.path.join(output_file_dir, 'reup_output')
        env = {'PERU_REUP_OUTPUT': output_path}
        await _plugin_job(plugin_context, module_type, module_fields, 'reup',
                          env, display_handle)
        with open(output_path) as output_file:
            fields = yaml.safe_load(output_file) or {}

    for key, value in fields.items():
        if not isinstance(key, str):
            raise PluginModuleFieldError(
                'reup field name must be a string: {}'.format(key))
        if not isinstance(value, str):
            raise PluginModuleFieldError(
                'reup field value must be a string: {}'.format(value))

    return fields


# Normally we prefer to execute plugins directly. This is pretty reliable on
# Unix, where scripts can specify their interpreter with a shebang line.
# However, it's not as reliable on Windows, because the extension-interpreter
# mapping is a global config. In my experience, installing and uninstalling a
# series of different Python interepreter versions on a Windows machine can
# break that association, and as a result break peru, in confusing ways. (Tests
# have also been broken by default for this reason on every Windows CI provider
# I've ever tried.)
#
# To work around this problem, we apply an extra heuristic on Windows: If a
# plugin executable filename ends in .py, assume that we should re-execute the
# current interpreter (sys.executable) to run that file, rather than relying on
# the system shell to find the interpreter. This fixes peru on systems with
# broken Python configs, and it makes no difference in the vast majority of
# other cases.
#
# For users who want to control this heuristic (either to disable it, or to
# force the same behavior on Unix), we define the PERU_REEXEC_PYTHON env var.
def _plugin_command(plugin_exe):
    config = os.environ.get("PERU_REEXEC_PYTHON", "default")
    if config == "always":
        reexec_heuristic = True
    elif config == "never":
        reexec_heuristic = False
    elif config == "default":
        reexec_heuristic = (os.name == 'nt')  # Windows
    else:
        raise RuntimeError("Unrecognized value for PERU_REEXEC_PYTHON", config)

    is_py_file = os.path.splitext(plugin_exe)[1] == ".py"

    if reexec_heuristic and is_py_file:
        # This is a .py file, and we're going to re-exec the current
        # interpreter to run it. This branch is the default for .py files on
        # Windows. On Unix, this requires PERU_REEXEC_PYTHON=always.
        return [sys.executable, plugin_exe], False
    elif os.name == 'nt':
        # This is Windows, but we're not going to re-exec the current
        # interpreter, either because this isn't a .py file or because
        # PERU_REEXEC_PYTHON=never. To allow the shell to find an interpreter,
        # we have to escape the path into a shell string and execute the child
        # process in shell mode.
        return subprocess.list2cmdline([plugin_exe]), True
    else:
        # Execute the file directly. This is the default on Unix and for
        # non-.py files on Windows.
        return [plugin_exe], False


async def _plugin_job(plugin_context, module_type, module_fields, command, env,
                      display_handle):
    # We take several locks and other context managers in here. Using an
    # AsyncExitStack saves us from indentation hell.
    async with AsyncExitStack() as stack:
        definition = _get_plugin_definition(module_type, module_fields,
                                            command)
        plugin_exe = _get_plugin_exe(definition, command)

        # The PERU_REEXEC_PYTHON heuristic happens here.
        plugin_command, is_shell_mode = _plugin_command(plugin_exe)

        complete_env = _plugin_env(plugin_context, definition, module_fields,
                                   command, stack)
        complete_env.update(env)

        # Use a lock to protect the plugin cache. It would be unsafe for two
        # jobs to read/write to the same plugin cache dir at the same time. The
        # lock (and the cache dir) are both keyed off the module's "cache
        # fields" as defined by plugin.yaml. For plugins that don't define
        # cacheable fields, there is no cache dir (it's set to /dev/null) and
        # the cache lock is a no-op.
        await stack.enter_async_context(
            _plugin_cache_lock(plugin_context, definition, module_fields))

        # Use a semaphore to limit the number of jobs that can run in parallel.
        # Most plugin fetches hit the network, and for performance reasons we
        # don't want to fire off too many network requests at once. See
        # DEFAULT_PARALLEL_FETCH_LIMIT. This also lets the user control
        # parallelism with the --jobs flag. It's important that this is the
        # last lock taken before starting a job, otherwise we might waste a job
        # slot just waiting on other locks.
        await stack.enter_async_context(plugin_context.parallelism_semaphore)

        # We use this debug counter for our parallelism tests. It's important
        # that it comes after all locks have been taken (so the job it's
        # counting is actually running).
        stack.enter_context(debug_parallel_count_context())

        try:
            await create_subprocess_with_handle(
                plugin_command,
                display_handle,
                cwd=plugin_context.cwd,
                env=complete_env,
                shell=is_shell_mode)
        except subprocess.CalledProcessError as e:
            raise PluginRuntimeError(module_type, module_fields, e.returncode,
                                     e.output)


def _get_plugin_exe(definition, command):
    if command == 'sync':
        exe = definition.sync_exe
    elif command == 'reup':
        exe = definition.reup_exe
    else:
        raise RuntimeError('Unrecognized command name: ' + repr(command))

    if not exe:
        raise PluginPermissionsError("Module type '{0}' does not support {1}.",
                                     definition.type, command)
    if not os.path.exists(exe):
        raise PluginPermissionsError('Plugin exe is missing: ' + exe)
    if not os.access(exe, os.X_OK):
        raise PluginPermissionsError('Plugin exe is not executable: ' + exe)
    return exe


def _format_module_fields(module_fields):
    return {
        'PERU_MODULE_{}'.format(name.upper()): value
        for name, value in module_fields.items()
    }


def _validate_plugin_definition(definition, module_fields):
    field_names_not_strings = [
        name for name in definition.fields if not isinstance(name, str)
    ]
    if field_names_not_strings:
        raise PluginModuleFieldError('Metadata field names must be strings: ' +
                                     ', '.join(
                                         repr(name)
                                         for name in field_names_not_strings))

    missing_module_fields = definition.required_fields - module_fields.keys()
    if missing_module_fields:
        raise PluginModuleFieldError('Required module field missing: ' +
                                     ', '.join(missing_module_fields))

    unknown_module_fields = module_fields.keys() - definition.fields
    if unknown_module_fields:
        raise PluginModuleFieldError('Unknown module fields: ' +
                                     ', '.join(unknown_module_fields))


def _plugin_env(plugin_context, plugin_definition, module_fields, command,
                exit_stack):
    env = os.environ.copy()

    # First, blank out all module field vars.  This prevents the calling
    # environment from leaking in when optional fields are undefined.
    blank_module_vars = {field: '' for field in plugin_definition.fields}
    env.update(_format_module_fields(blank_module_vars))
    # Then add in the fields that are actually defined.
    env.update(_format_module_fields(module_fields))

    # Disable buffering by default in Python subprocesses. Without this,
    # plugins would usually need to do something like
    #     print(..., flush=True)
    # or else all their progress output would get held up in the stdout buffer
    # until the plugin finally exited. Plugins in other languages will need to
    # be careful about this.
    env['PYTHONUNBUFFERED'] = 'true'

    # For plugins that use the same exe for sync and reup, make the command
    # name available in the environment.
    env['PERU_PLUGIN_COMMAND'] = command

    # Create a directory for plugins' temporary files.
    env['PERU_PLUGIN_TMP'] = exit_stack.enter_context(tmp_dir(plugin_context))

    # Create a persistent cache dir for saved files, like repo clones.
    env['PERU_PLUGIN_CACHE'] = _plugin_cache_path(
        plugin_context, plugin_definition, module_fields)

    return env


def _noop_lock():
    return AsyncExitStack()  # a no-op context manager


def _plugin_cache_lock(plugin_context, definition, module_fields):
    if not definition.cache_fields:
        # This plugin is not cacheable.
        return _noop_lock()
    key = _plugin_cache_key(definition, module_fields)
    return plugin_context.plugin_cache_locks[key]


def _plugin_cache_path(plugin_context, definition, module_fields):
    if not definition.cache_fields:
        # This plugin is not cacheable.
        return os.devnull
    key = _plugin_cache_key(definition, module_fields)
    plugin_cache = os.path.join(plugin_context.plugin_cache_root,
                                definition.type, key)
    makedirs(plugin_cache)
    return plugin_cache


def _plugin_cache_key(definition, module_fields):
    assert definition.cache_fields, "Can't compute key for uncacheable type."
    return cache.compute_key({
        'type': definition.type,
        'cacheable_fields': {
            field: module_fields.get(field, None)
            for field in definition.cache_fields
        },
    })


def _get_plugin_definition(module_type, module_fields, command):
    root = _find_plugin_dir(module_type)
    metadata_path = os.path.join(root, 'plugin.yaml')
    if not os.path.isfile(metadata_path):
        raise PluginMetadataMissingError(
            'No metadata file found for plugin at path: {}'.format(root))

    # Read the metadata document.
    with open(metadata_path) as metafile:
        metadoc = yaml.safe_load(metafile) or {}
    sync_exe = os.path.join(root, metadoc.pop('sync exe'))
    reup_exe = (None if 'reup exe' not in metadoc else os.path.join(
        root, metadoc.pop('reup exe')))
    required_fields = frozenset(metadoc.pop('required fields'))
    optional_fields = frozenset(metadoc.pop('optional fields', []))
    cache_fields = frozenset(metadoc.pop('cache fields', []))
    fields = required_fields | optional_fields
    # TODO: All of these checks need to be tested.
    if metadoc:
        raise RuntimeError('Unknown metadata in {} plugin: {}'.format(
            module_type, metadoc))
    overlap = required_fields & optional_fields
    if overlap:
        raise RuntimeError(
            'Fields in {} are both required and optional: {}'.format(
                module_type, overlap))
    invalid = cache_fields - fields
    if invalid:
        raise RuntimeError(
            '"cache fields" must also be either required or optional: ' +
            str(invalid))

    definition = PluginDefinition(module_type, sync_exe, reup_exe, fields,
                                  required_fields, optional_fields,
                                  cache_fields)
    _validate_plugin_definition(definition, module_fields)
    return definition


def _find_plugin_dir(module_type):
    '''Find the directory containing the plugin definition for the given type.
    Do this by searching all the paths where plugins can live for a dir that
    matches the type name.'''

    for install_dir in _get_plugin_install_dirs():
        candidate = os.path.join(install_dir, module_type)
        if os.path.isdir(candidate):
            return candidate
    else:
        raise PluginCandidateError(
            'No plugin found for `{}` module in paths:\n{}'.format(
                module_type, '\n'.join(_get_plugin_install_dirs())))


def _get_plugin_install_dirs():
    '''Return all the places on the filesystem where we should look for plugin
    definitions. Order is significant here: user-installed plugins should be
    searched first, followed by system-installed plugins, and last of all peru
    builtins.'''
    builtins_dir = os.path.join(compat.MODULE_ROOT, 'resources', 'plugins')
    if os.name == 'nt':
        # Windows
        local_data_dir = os.path.expandvars('%LOCALAPPDATA%')
        program_files_dir = os.path.expandvars('%PROGRAMFILES%')
        return (
            os.path.join(local_data_dir, 'peru', 'plugins'),
            os.path.join(program_files_dir, 'peru', 'plugins'),
            builtins_dir,
        )
    else:
        # non-Windows
        default_config_dir = os.path.expanduser('~/.config')
        config_dir = os.environ.get('XDG_CONFIG_HOME', default_config_dir)
        return (
            os.path.join(config_dir, 'peru', 'plugins'),
            '/usr/local/lib/peru/plugins',
            '/usr/lib/peru/plugins',
            builtins_dir,
        )


def debug_assert_clean_parallel_count():
    assert DEBUG_PARALLEL_COUNT == 0, \
        "parallel count should be 0 but it's " + str(DEBUG_PARALLEL_COUNT)


@contextlib.contextmanager
def debug_parallel_count_context():
    global DEBUG_PARALLEL_COUNT, DEBUG_PARALLEL_MAX
    DEBUG_PARALLEL_COUNT += 1
    DEBUG_PARALLEL_MAX = max(DEBUG_PARALLEL_COUNT, DEBUG_PARALLEL_MAX)
    try:
        yield
    finally:
        DEBUG_PARALLEL_COUNT -= 1


def tmp_dir(context):
    return tempfile.TemporaryDirectory(dir=context.tmp_root)


class PluginCandidateError(PrintableError):
    pass


class PluginCommandCandidateError(PrintableError):
    pass


class PluginModuleFieldError(PrintableError):
    pass


class PluginMetadataMissingError(PrintableError):
    pass


class PluginPermissionsError(PrintableError):
    pass


class PluginRuntimeError(PrintableError):
    def __init__(self, type, fields, errorcode, output):
        # Don't depend on plugins using terminating newlines.
        stripped_output = output.strip('\n')
        super().__init__(stripped_output)

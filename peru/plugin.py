import asyncio
from asyncio import subprocess
import codecs
from collections import namedtuple
import contextlib
import io
import os
import sys
import tempfile
import textwrap

import yaml

from . import cache
from .compat import makedirs
from .error import PrintableError

DEFAULT_PARALLEL_FETCH_LIMIT = 10

DEBUG_PARALLEL_COUNT = 0
DEBUG_PARALLEL_MAX = 0

# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
PLUGINS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'resources', 'plugins'))

PluginDefinition = namedtuple(
    'PluginDefinition',
    ['type', 'fetch_exe', 'reup_exe', 'fields', 'required_fields',
     'optional_fields', 'cache_fields'])

PluginContext = namedtuple(
    'PluginContext',
    ['cwd', 'plugin_cache_root', 'plugin_paths', 'parallelism_semaphore',
     'plugin_cache_locks', 'tmp_dir'])


@asyncio.coroutine
def plugin_fetch(plugin_context, module_type, module_fields, dest,
                 display_handle):
    env = {'PERU_FETCH_DEST': dest}
    yield from _plugin_job(plugin_context, module_type, module_fields, 'fetch',
                           env, display_handle)


@asyncio.coroutine
def plugin_get_reup_fields(plugin_context, module_type, module_fields,
                           display_handle):
    with tempfile.NamedTemporaryFile(dir=plugin_context.tmp_dir) as tmp:
        output_path = tmp.name
        env = {'PERU_REUP_OUTPUT': output_path}
        yield from _plugin_job(
            plugin_context, module_type, module_fields, 'reup', env,
            display_handle)
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


@asyncio.coroutine
def _plugin_job(plugin_context, module_type, module_fields, command, env,
                display_handle):
    global DEBUG_PARALLEL_COUNT, DEBUG_PARALLEL_MAX

    definition = _get_plugin_definition(module_type, module_fields, command,
                                        plugin_context.plugin_paths)

    exe = _get_plugin_exe(definition, command)

    complete_env = _plugin_env(definition, module_fields, command)
    complete_env.update({
        'PERU_PLUGIN_CACHE': _plugin_cache_path(
            plugin_context, definition, module_fields)})
    complete_env.update(env)

    # Use stdout's encoding, but provide a default for the case where stdout
    # has been redirected to a StringIO. (This happens in tests.)
    decoder = codecs.getincrementaldecoder(sys.stdout.encoding or 'utf8')(
        errors='replace')
    output_copy = io.StringIO()

    # Use a lock to protect the plugin cache. It would be unsafe for two jobs
    # to read/write to the same plugin cache dir at the same time. The lock
    # (and the cache dir) are both keyed off the module's "cache fields" as
    # defined by plugin.yaml. For plugins that don't define cacheable fields,
    # there is no cache dir (it's set to /dev/null) and the cache lock is a
    # no-op.
    cache_lock = _plugin_cache_lock(plugin_context, definition, module_fields)
    with (yield from cache_lock):
        # Use a semaphore to limit the number of jobs that can run in parallel.
        # Most plugin fetches hit the network, and for performance reasons we
        # don't want to fire off too many network requests at once. See
        # DEFAULT_PARALLEL_FETCH_LIMIT. This also lets the user control
        # parallelism with the --jobs flag.
        with (yield from plugin_context.parallelism_semaphore):
            # Now that the job is really starting, open the output handle.
            with display_handle:
                DEBUG_PARALLEL_COUNT += 1
                DEBUG_PARALLEL_MAX = max(
                    DEBUG_PARALLEL_COUNT, DEBUG_PARALLEL_MAX)
                proc = yield from asyncio.create_subprocess_exec(
                    exe, cwd=plugin_context.cwd, env=complete_env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL)
                while True:
                    outputbytes = yield from proc.stdout.read(4096)
                    if not outputbytes:
                        break
                    outputstr = decoder.decode(outputbytes)
                    display_handle.write(outputstr)
                    output_copy.write(outputstr)
                yield from proc.wait()
                DEBUG_PARALLEL_COUNT -= 1
    if proc.returncode != 0:
        raise PluginRuntimeError(module_type, module_fields, proc.returncode,
                                 output_copy.getvalue())
    assert not decoder.buffer, 'decoder nonempty: ' + repr(decoder.buffer)


def _get_plugin_exe(definition, command):
    if command == 'fetch':
        exe = definition.fetch_exe
    elif command == 'reup':
        exe = definition.reup_exe
    else:
        raise RuntimeError('Unrecognized command name: ' + repr(command))

    if not os.path.exists(exe):
        raise PluginPermissionsError('Plugin exe does not exist: ' + exe)
    if not os.access(exe, os.X_OK):
        raise PluginPermissionsError('Plugin exe is not executable: ' + exe)
    return exe


def _format_module_fields(module_fields):
    return {'PERU_MODULE_{}'.format(name.upper()): value for
            name, value in module_fields.items()}


def _validate_plugin_definition(definition, module_fields):
    field_names_not_strings = [name for name in definition.fields
                               if not isinstance(name, str)]
    if field_names_not_strings:
        raise PluginModuleFieldError(
            'Metadata field names must be strings: ' +
            ', '.join(repr(name) for name in field_names_not_strings))

    missing_module_fields = definition.required_fields - module_fields.keys()
    if missing_module_fields:
        raise PluginModuleFieldError(
            'Required module field missing: ' +
            ', '.join(missing_module_fields))

    unknown_module_fields = module_fields.keys() - definition.fields
    if unknown_module_fields:
        raise PluginModuleFieldError(
            'Unknown module fields: ' + ', '.join(unknown_module_fields))


def _plugin_env(definition, module_fields, command):
    env = os.environ.copy()

    # First, blank out all module field vars.  This prevents the calling
    # environment from leaking in when optional fields are undefined.
    blank_module_vars = {field: '' for field in definition.fields}
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

    # For plugins that use the same exe for fetch and reup, make the command
    # name available in the environment.
    env['PERU_PLUGIN_COMMAND'] = command

    return env


@asyncio.coroutine
def _noop_lock():
    return contextlib.ExitStack()  # a no-op context manager


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
    plugin_cache = os.path.join(
        plugin_context.plugin_cache_root, definition.type, key)
    makedirs(plugin_cache)
    return plugin_cache


def _plugin_cache_key(definition, module_fields):
    assert definition.cache_fields, "Can't compute key for uncacheable type."
    return cache.compute_key({
        'type': definition.type,
        'cacheable_fields': {field: module_fields.get(field, None)
                             for field in definition.cache_fields},
    })


def _get_plugin_definition(module_type, module_fields, command, plugin_paths):
    root = _find_plugin_dir(module_type, plugin_paths)
    metadata_path = os.path.join(root, 'plugin.yaml')
    if not os.path.isfile(metadata_path):
        raise PluginMetadataMissingError(
            'No metadata file found for plugin at path: {}'.format(root))

    # Read the metadata document.
    with open(metadata_path) as metafile:
        metadoc = yaml.safe_load(metafile) or {}
    fetch_exe = os.path.join(root, metadoc.pop('fetch exe'))
    reup_exe = (None if 'reup exe' not in metadoc
                else os.path.join(root, metadoc.pop('reup exe')))
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
        raise RuntimeError('Fields in {} are both required and optional: {}'
                           .format(module_type, overlap))
    invalid = cache_fields - fields
    if invalid:
        raise RuntimeError(
            '"cache fields" must also be either required or optional: ' +
            str(invalid))

    definition = PluginDefinition(
        module_type, fetch_exe, reup_exe, fields, required_fields,
        optional_fields, cache_fields)
    _validate_plugin_definition(definition, module_fields)
    return definition


def _find_plugin_dir(module_type, plugin_paths):
    '''Find the directory containing the plugin definition for the given type.
    Do this by searching all the paths where plugins can live for a dir that
    matches the type name.'''
    roots = [PLUGINS_DIR] + list(plugin_paths)
    options = [os.path.join(root, module_type) for root in roots]
    matches = [option for option in options if os.path.isdir(option)]

    if not matches:
        raise PluginCandidateError(
            'No plugin found for `{}` module in paths:\n{}'.format(
                module_type,
                '\n'.join(roots)))
    if len(matches) > 1:
        raise PluginCandidateError(
            'Multiple plugins found for `{}` module:\n{}'.format(
                module_type,
                '\n'.join(matches)))

    return matches[0]


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
        formatted_fields = '\n'.join('    {}: {}'.format(name, val)
                                     for name, val in fields.items())
        super().__init__(textwrap.dedent('''\
            {} plugin exited with error code {}.
            Fields:
            {}
            Output:
            {}''').format(type, errorcode, formatted_fields, output))

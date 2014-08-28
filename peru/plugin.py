import asyncio
from asyncio import subprocess
from collections import namedtuple
import os
from subprocess import CalledProcessError

import yaml

from .compat import makedirs
from .error import PrintableError

DEFAULT_PARALLEL_FETCH_LIMIT = 10

# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
PLUGINS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'resources', 'plugins'))

PluginDefinition = namedtuple(
    'PluginDefinition',
    ['executable_path', 'fields', 'required_fields', 'optional_fields'])

PluginContext = namedtuple(
    'PluginContext',
    ['cwd', 'plugin_cache_root', 'plugin_paths', 'parallelism_semaphore'])


@asyncio.coroutine
def plugin_fetch(plugin_context, module_type, module_fields, dest, *,
                 capture_output=False, stderr_to_stdout=False):
    definition = _get_plugin_definition(
        module_type, module_fields, 'fetch', plugin_context.plugin_paths)

    env = _plugin_env(definition, module_fields)
    env.update({
        'PERU_FETCH_DEST': dest,
        'PERU_PLUGIN_CACHE': _plugin_cache_path(
            plugin_context.plugin_cache_root,
            module_type)})
    stderr = subprocess.STDOUT if stderr_to_stdout else None
    stdout = subprocess.PIPE if capture_output else None

    with (yield from plugin_context.parallelism_semaphore):
        proc = yield from asyncio.create_subprocess_exec(
            definition.executable_path, cwd=plugin_context.cwd, env=env,
            stdout=stdout, stderr=stderr)
        output, _ = yield from proc.communicate()
    if output is not None:
        output = output.decode('utf8')
    _throw_if_error(proc, definition.executable_path, output)
    return output


@asyncio.coroutine
def plugin_get_reup_fields(plugin_context, module_type, module_fields):
    definition = _get_plugin_definition(
        module_type, module_fields, 'reup', plugin_context.plugin_paths)

    env = _plugin_env(definition, module_fields)
    env.update({
        'PERU_PLUGIN_CACHE': _plugin_cache_path(
            plugin_context.plugin_cache_root,
            module_type)})

    with (yield from plugin_context.parallelism_semaphore):
        proc = yield from asyncio.create_subprocess_exec(
            definition.executable_path, stdout=subprocess.PIPE,
            cwd=plugin_context.cwd, env=env)
        output, _ = yield from proc.communicate()
    output = output.decode('utf8')
    _throw_if_error(proc, definition.executable_path, output)
    fields = yaml.safe_load(output) or {}

    for key, value in fields.items():
        if not isinstance(key, str):
            raise PluginModuleFieldError(
                'reup field name must be a string: {}'.format(key))
        if not isinstance(value, str):
            raise PluginModuleFieldError(
                'reup field value must be a string: {}'.format(value))

    return fields


def _throw_if_error(proc, command, output):
    if proc.returncode != 0:
        raise CalledProcessError(proc, command, output)


def _format_module_fields(module_fields):
    return {'PERU_MODULE_{}'.format(name.upper()): value for
            name, value in module_fields.items()}


def _validate_plugin_definition(definition, module_fields):
    if not os.access(definition.executable_path, os.X_OK):
        raise PluginPermissionsError(
            'Plugin command is not executable: ' + definition.executable_path)
    if not all(isinstance(field, str) for field in definition.fields):
        raise PluginModuleFieldError(
            'Metadata field names must be strings.')
    if not all(field in module_fields for field in definition.required_fields):
        raise PluginModuleFieldError('Required module field missing.')
    if any(key not in definition.fields for key in module_fields.keys()):
        raise PluginModuleFieldError('Unexpected module field.')


def _plugin_env(definition, module_fields):
    env = os.environ.copy()
    env.update({field: '' for field in definition.optional_fields})
    env.update(_format_module_fields(module_fields))
    return env


def _plugin_cache_path(plugin_cache_root, module_type):
    plugin_cache = os.path.join(plugin_cache_root, module_type)
    makedirs(plugin_cache)
    return plugin_cache


def _get_plugin_definition(module_type, module_fields, command, plugin_paths):
    executable_path, metadata_path = _find_plugin_files(
        module_type, command, plugin_paths)

    # Read the metadata document.
    with open(metadata_path) as metafile:
        metadoc = yaml.safe_load(metafile) or {}
    required_fields = frozenset(metadoc.pop('required fields', []))
    optional_fields = frozenset(metadoc.pop('optional fields', []))
    fields = required_fields | optional_fields
    if metadoc:
        raise RuntimeError('Unknown metadata in {} plugin: {}'.format(
            module_type, metadoc))
    overlap = required_fields & optional_fields
    if overlap:
        raise RuntimeError('Fields in {} are both required and optional: {}'
                           .format(module_type, overlap))

    definition = PluginDefinition(
        executable_path, fields, required_fields, optional_fields)
    _validate_plugin_definition(definition, module_fields)
    return definition


def _find_plugin_files(module_type, command, plugin_paths):
    root = _find_plugin_dir(module_type, plugin_paths)

    # Scan for executable files in the directory. The command is used as a
    # prefix, not an exact match, to support extensions. This is mainly because
    # extensions are mandatory on Windows.
    matches = [match for match in os.listdir(root) if
               match.startswith(command) and
               os.path.isfile(os.path.join(root, match))]

    # Ensure there is exactly one match. It is possible for multiple files to
    # share the command prefix, and we don't want to have to guess.
    if not(matches):
        raise PluginCommandCandidateError(
            'No candidate for command `{}`.'.format(command))
    if len(matches) > 1:
        # Barf if there is more than one candidate.
        raise PluginCommandCandidateError(
            'More than one candidate for command `{}`.'.format(command))
    executable_path = os.path.join(root, matches[0])

    # Look for a metadata file.
    metadata_path = os.path.join(root, 'plugin.yaml')
    if not os.path.isfile(metadata_path):
        raise PluginMetadataMissingError(
            'No metadata file found for plugin at path: {}'.format(root))

    return (executable_path, metadata_path)


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

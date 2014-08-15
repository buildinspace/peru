import asyncio
from asyncio import subprocess
from collections import namedtuple
import os
from subprocess import CalledProcessError

import yaml

from .compat import makedirs
from .error import PrintableError


# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
PLUGINS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'resources', 'plugins'))


# TODO: There's a lot of loose data moving between these functions. It would
# probably be good to use some bona fide objects to wrap this stuff up, since
# this composition is broken. PluginInvocation may want to include data like
# the module fields too, for example.
PluginInvocation = namedtuple('PluginInvocation', ['path', 'metadata'])
PluginMetadata = namedtuple(
    'PluginMetadata', ['required_fields', 'optional_fields'])


@asyncio.coroutine
def plugin_fetch(cwd, plugin_cache_root, dest, module_type, module_fields, *,
                 capture_output=False, stderr_to_stdout=False,
                 plugin_roots=()):
    invocation = _plugin_invocation(
        module_type, module_fields, 'fetch', plugin_roots)

    env = _plugin_env(invocation, module_fields)
    env.update({
        'PERU_FETCH_DEST': dest,
        'PERU_PLUGIN_CACHE': _plugin_cache_path(
            plugin_cache_root,
            module_type)})
    stderr = subprocess.STDOUT if stderr_to_stdout else None
    stdout = subprocess.PIPE if capture_output else None

    proc = yield from asyncio.create_subprocess_exec(
        invocation.path, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
    output, _ = yield from proc.communicate()
    if output is not None:
        output = output.decode('utf8')
    _throw_if_error(proc, invocation.path, output)
    return output


@asyncio.coroutine
def plugin_get_reup_fields(cwd, plugin_cache_root, module_type, module_fields,
                           *, plugin_roots=()):
    invocation = _plugin_invocation(
        module_type, module_fields, 'reup', plugin_roots)

    env = _plugin_env(invocation, module_fields)
    env.update({
        'PERU_PLUGIN_CACHE': _plugin_cache_path(
            plugin_cache_root,
            module_type)})

    proc = yield from asyncio.create_subprocess_exec(
        invocation.path, stdout=subprocess.PIPE, cwd=cwd, env=env)
    output, _ = yield from proc.communicate()
    output = output.decode('utf8')
    _throw_if_error(proc, invocation.path, output)
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


def _validate_plugin_invocation(invocation, module_fields):
    path = invocation.path
    if not os.access(path, os.X_OK):
        raise PluginPermissionsError(
            'Plugin command is not executable: {}'.format(path))

    required = invocation.metadata.required_fields
    optional = invocation.metadata.optional_fields
    fields = required + optional
    if not all(isinstance(field, str) for field in fields):
        raise PluginModuleFieldError(
            'Metadata field names must be strings.')
    if not all(field in module_fields for field in required):
        raise PluginModuleFieldError('Required module field missing.')
    if any(key not in fields for key in module_fields.keys()):
        raise PluginModuleFieldError('Unexpected module field.')


def _plugin_env(invocation, module_fields):
    env = os.environ.copy()
    env.update({field: '' for field in invocation.metadata.optional_fields})
    env.update(_format_module_fields(module_fields))

    return env


def _plugin_cache_path(plugin_cache_root, module_type):
    plugin_cache = os.path.join(plugin_cache_root, module_type)
    makedirs(plugin_cache)
    return plugin_cache


def _plugin_invocation(module_type, module_fields, command, plugin_roots):
    # Get paths to the executable and metadata files.
    path, metapath = _plugin_manifest(module_type, command, plugin_roots)

    # Read the metadata document.
    with open(metapath) as metafile:
        metadoc = yaml.safe_load(metafile) or {}
    metadata = PluginMetadata(
        metadoc.get('required fields') or [],
        metadoc.get('optional fields') or [])

    invocation = PluginInvocation(path, metadata)

    _validate_plugin_invocation(invocation, module_fields)
    return invocation


def _plugin_manifest(module_type, command, plugin_roots):
    root = _plugin_root_path(module_type, plugin_roots)

    # Scan for executable files in the directory. The command is used as a
    # prefix, not an exact match, to support extensions. To support certain
    # platforms, an extension is necessary for execution as a subprocess. Most
    # notably, this is required to support Windows.
    matches = [match for match in os.listdir(root) if
               match.startswith(command) and
               os.path.isfile(os.path.join(root, match))]

    # Ensure there is only one match. It is possible for multiple files to
    # share the command prefix.
    if not(matches):
        raise PluginCommandCandidateError(
            'No candidate for command `{}`.'.format(command))
    if len(matches) > 1:
        # Barf if there is more than one candidate.
        raise PluginCommandCandidateError(
            'More than one candidate for command `{}`.'.format(command))

    # Look for a metadata file.
    metadata = os.path.join(root, 'plugin.yaml')
    if not os.path.isfile(metadata):
        raise PluginMetadataMissingError(
            'No metadata file found for plugin at path: {}'.format(root))

    return (os.path.join(root, matches[0]), metadata)


def _plugin_root_path(module_type, plugin_roots):
    roots = [PLUGINS_DIR] + list(plugin_roots)
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

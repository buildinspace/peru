import os
import subprocess

import yaml

from .compat import makedirs
from .error import PrintableError


# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
PLUGINS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "resources", "plugins"))


def plugin_fetch(cwd, plugins_cache_root, type, dest, plugin_fields, *,
                 capture_output=False, stderr_to_stdout=False,
                 plugin_roots=()):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, 'fetch', plugin_roots, plugin_fields,
                              dest, cache_path)

    kwargs = {"stderr": subprocess.STDOUT} if stderr_to_stdout else {}
    if capture_output:
        output = subprocess.check_output(command, cwd=cwd, **kwargs)
        return output.decode('utf8')
    else:
        subprocess.check_call(command, cwd=cwd, **kwargs)


def plugin_get_reup_fields(cwd, plugins_cache_root, type, plugin_fields, *,
                           plugin_roots=()):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, 'reup', plugin_roots, plugin_fields,
                              cache_path)
    output = subprocess.check_output(command, cwd=cwd).decode('utf8')
    new_fields = yaml.safe_load(output) or {}
    for key, val in new_fields.items():
        assert isinstance(key, str), 'Reup fields must always be strings.'
        assert isinstance(val, str), 'Reup values must always be strings.'
    return new_fields


def _plugin_command(type, subcommand, plugin_roots, plugin_fields, *args):
    path = _plugin_exe_path(type, subcommand, plugin_roots)

    assert os.access(path, os.X_OK), type + " plugin isn't executable."
    assert "--" not in plugin_fields, "-- is not a valid field name"

    command = [path]
    for field_name in sorted(plugin_fields.keys()):
        command.append(field_name)
        command.append(plugin_fields[field_name])
    command.append("--")
    command.extend(args)

    return command


def _plugin_cache_path(plugins_cache_root, type):
    plugin_cache = os.path.join(plugins_cache_root, type)
    makedirs(plugin_cache)
    return plugin_cache


def _plugin_exe_path(type, subcommand, plugin_roots):
    root = _find_plugin(type, plugin_roots)

    # Scan for files in the script dir. The subcommand is used as a prefix, not
    # an exact match, to support extensions. To support certain platforms, an
    # extension is necessary for execution as a subprocess. Most notably, this
    # is required to support Windows.
    matches = [match for match in os.listdir(root) if
               match.startswith(subcommand) and
               os.path.isfile(os.path.join(root, match))]

    # Ensure there is only one match. It is possible for multiple files to
    # share the subcommand prefix.
    if not(matches):
        raise PluginCommandMissingError(
            'no candidate for command `{}`'.format(subcommand))
    if len(matches) > 1:
        # Barf if there is more than one candidate.
        raise MultiplePluginCommandsError(
            'more than one candidate for command `{}`'.format(subcommand))

    return os.path.join(root, matches[0])


def _find_plugin(type, plugin_roots):
    roots = [PLUGINS_DIR] + list(plugin_roots)
    options = [os.path.join(root, type) for root in roots]
    matches = [option for option in options if os.path.isdir(option)]
    if not matches:
        raise PluginMissingError(
            'No plugin "{}" found at any of the following roots:\n'
            .format(type) +
            '\n'.join(roots))
    if len(matches) > 1:
        raise MultiplePluginsError(
            'Multiple plugins found of type "{}":\n'.format(type) +
            '\n'.join(matches))
    return matches[0]


class PluginMissingError(PrintableError):
    pass


class MultiplePluginsError(PrintableError):
    pass


class PluginCommandMissingError(PrintableError):
    pass


class MultiplePluginCommandsError(PrintableError):
    pass

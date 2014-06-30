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
    os.path.join(os.path.dirname(__file__), "plugins"))


def plugin_fetch(plugins_cache_root, type, dest, plugin_fields, *,
                 capture_output=False, stderr_to_stdout=False):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, 'fetch', plugin_fields, dest, cache_path)

    kwargs = {"stderr": subprocess.STDOUT} if stderr_to_stdout else {}
    if capture_output:
        output = subprocess.check_output(command, **kwargs)
        return output.decode('utf8')
    else:
        subprocess.check_call(command, **kwargs)


def plugin_get_reup_fields(plugins_cache_root, type, plugin_fields):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, 'reup', plugin_fields, cache_path)
    output = subprocess.check_output(command).decode('utf8')
    return yaml.load(output)


def _plugin_command(type, subcommand, plugin_fields, *args):
    path = _plugin_exe_path(type, subcommand)

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


def _plugin_exe_path(type, subcommand):
    # Scan for a corresponding script dir.
    root = os.path.join(PLUGINS_DIR, type)
    if not os.path.isdir(root):
        raise PrintableError(
            'no root directory found for plugin `{0}`'.format(type))

    # Scan for files in the script dir.
    # To support certain platforms, an extension is necessary for execution as a
    # subprocess.
    # The subcommand is used as a prefix, not an exact match, to support
    # extensions.
    matches = [match for match in os.listdir(root) if
               match.startswith(subcommand) and
               os.path.isfile(os.path.join(root, match))]

    # Ensure there is only one match.
    # It is possible for multiple files to share the subcommand prefix.
    if len(matches) is 0:
        raise PrintableError(
            'no candidate for command `{0}`'.format(subcommand))
    if len(matches) > 1:
        # Barf if there is more than one candidate.
        raise PrintableError(
            'more than one candidate for command `{0}`'.format(subcommand))

    return os.path.join(root, matches[0])

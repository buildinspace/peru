import os
import subprocess

import yaml

from .compat import makedirs


# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
PLUGINS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "plugins"))


def plugin_fetch(plugins_cache_root, type, dest, plugin_fields, *,
                 capture_output=False, stderr_to_stdout=False):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, plugin_fields, "fetch", dest, cache_path)

    kwargs = {"stderr": subprocess.STDOUT} if stderr_to_stdout else {}
    if capture_output:
        output = subprocess.check_output(command, **kwargs)
        return output.decode('utf8')
    else:
        subprocess.check_call(command, **kwargs)


def plugin_get_reup_fields(plugins_cache_root, type, plugin_fields):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, plugin_fields, "reup", cache_path)
    output = subprocess.check_output(command).decode('utf8')
    return yaml.load(output)


def _plugin_command(type, plugin_fields, *args):
    path = _plugin_exe_path(type)
    assert os.path.isfile(path), type + " plugin doesn't exist at path " + path
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


def _plugin_exe_path(type):
    """Plugins can end in any extension. (.py, .sh, etc.) So we have to look
    for plugin executables that *start* with the name of the plugin. If we find
    more than one, error out."""
    plugins = os.listdir(PLUGINS_DIR)
    plugin_start = type + "_plugin."
    matches = [name for name in plugins if name.startswith(plugin_start)]
    assert len(matches) > 0, "plugin " + type + " doesn't exist"
    assert len(matches) == 1, "more than one candidate for plugin " + type
    path = os.path.join(PLUGINS_DIR, matches[0])
    return path

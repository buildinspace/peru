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
                 capture_output=False):
    cache_path = _plugin_cache_path(plugins_cache_root, type)
    command = _plugin_command(type, plugin_fields, "fetch", dest, cache_path)

    if capture_output:
        output = subprocess.check_output(command)
        return output.decode('utf8')
    else:
        subprocess.check_call(command)


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
    path = os.path.join(PLUGINS_DIR, type + "_plugin.py")
    return path

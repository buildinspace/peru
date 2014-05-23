import os
import subprocess

import yaml


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
    assert os.path.isfile(path), type + " plugin doesn't exist."
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
    os.makedirs(plugin_cache, exist_ok=True)
    return plugin_cache


def _plugin_exe_path(type):
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    path = os.path.join(plugins_dir, type + "_plugin.py")
    return path

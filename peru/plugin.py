import os
import subprocess


def plugin_path(type):
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    path = os.path.join(plugins_dir, type + "_plugin.py")
    return path


def plugin_fetch(cache, type, dest, plugin_fields):
    path = plugin_path(type)
    assert os.path.isfile(path), type + " plugin doesn't exist."
    assert os.access(path, os.X_OK), type + " plugin isn't executable."

    plugin_cache = os.path.join(cache.root, "plugins", type)
    os.makedirs(plugin_cache, exist_ok=True)
    env = dict(os.environ)
    env["PERU_PLUGIN_CACHE"] = plugin_cache

    command = [path, "fetch", dest]
    for field_name in sorted(plugin_fields.keys()):
        command.append(field_name)
        command.append(plugin_fields[field_name])

    subprocess.check_call(command, env=env)

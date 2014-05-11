import os
import subprocess
import sys


def plugin_path(type):
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    path = os.path.join(plugins_dir, type + "_plugin.py")
    return path


def plugin_fetch(cache_root, type, dest, plugin_fields, *, verbose=False):
    path = plugin_path(type)
    assert os.path.isfile(path), type + " plugin doesn't exist."
    assert os.access(path, os.X_OK), type + " plugin isn't executable."

    plugin_cache = os.path.join(cache_root, "plugins", type)
    os.makedirs(plugin_cache, exist_ok=True)

    command = [path, "--cache", plugin_cache, "fetch", dest]
    for field_name in sorted(plugin_fields.keys()):
        command.append("--" + field_name)
        command.append(plugin_fields[field_name])

    output = subprocess.check_output(command, stderr=subprocess.STDOUT)

    if verbose:
        sys.stdout.buffer.write(output)

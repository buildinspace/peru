import collections
import os

def _entry_point_kwargs(runtime, plugins):
    def plugin_register(name, *args, **kwargs):
        plugin = Plugin(name, *args, **kwargs)
        plugins[name] = plugin

    return {
        "register": plugin_register,
        "cache_root": runtime.cache.root,
        "verbose": runtime.verbose,
    }

def load_plugins(runtime):
    plugins_path = os.path.join(os.path.dirname(__file__), "plugins")
    plugins = {}

    for name in os.listdir(plugins_path):
        if not name.endswith("_plugin.py"):
            continue
        with open(os.path.join(plugins_path, name)) as f:
            code = f.read()
        env = {}
        exec(code, env)
        entry_point = env["peru_plugin_main"]
        entry_point(**_entry_point_kwargs(runtime, plugins))

    return plugins

class Plugin:
    def __init__(self, name, required_fields, optional_fields,
                 get_files_callback):
        self.name = name
        self.required_fields = required_fields
        self.optional_fields = optional_fields
        self.field_names = required_fields | optional_fields
        self.get_files_callback = get_files_callback

import collections
import os
import sys

def _entry_point_kwargs(runtime, plugins):
    def plugin_register(name, *args, **kwargs):
        plugin = Plugin(name, *args, **kwargs)
        plugins[name] = plugin

    return {
        # TODO: make this not a function
        "cache_root": lambda: runtime.cache.root,
        "register": plugin_register,
        "runtime": runtime,
        "verbose": runtime.verbose,
    }

def load_plugins(runtime):
    plugins_path = os.path.join(os.path.dirname(__file__), "plugins")
    plugins = {}

    # TODO: Be less evil.
    sys.path.append(plugins_path)

    for name in os.listdir(plugins_path):
        if not name.endswith("_plugin.py"):
            continue
        with open(os.path.join(plugins_path, name)) as f:
            code = f.read()
        plugin_module = __import__(name[:-3])
        entry_point = plugin_module.peru_plugin_main
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

    def extract_fields(self, blob, module_name):
        plugin_fields = {}
        for field in list(blob.keys()):
            if field in self.field_names:
                plugin_fields[field] = blob.pop(field)
        missing_fields = self.required_fields - plugin_fields.keys()
        if missing_fields:
            raise RuntimeError("{} module {} is missing fields: {}".format(
                self.name, module_name, ", ".join(missing_fields)))
        return plugin_fields

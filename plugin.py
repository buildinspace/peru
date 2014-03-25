import collections
import os

def _plugin_kwargs(runtime):
    return {
        "register": Plugin,
        "cache_root": runtime.peru_cache_root,
        "verbose": runtime.verbose,
    }

def load_plugins(runtime)
    global _plugins
    if _plugins is not None:
        return
    _plugins = {}
    path = os.path.join(os.path.dirname(__file__), "plugins")
    for name in os.listdir(_plugins_path):
        if not name.endswith("_plugin.py"):
            continue
        with open(os.path.join(_plugins_path, name)) as f:
            code = f.read()
        env = {}
        exec(code, env)
        entry_point = env["peru_plugin_main"]
        entry_point(**_plugin_kwargs(runtime))

class Plugin:
    def __init__(name, required_fields, optional_fields, callback):
        self.name = name
        self.required_fields = required_fields
        self.optional_fields = optional_fields
        self.field_names = required_fields | optional_fields
        self.callback = callback
        _plugins[name] = self

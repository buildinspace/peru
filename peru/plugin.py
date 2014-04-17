import pkgutil

from . import plugins


def _entry_point_kwargs(runtime, plugins_dict):
    def plugin_register(name, *args, **kwargs):
        plugin = Plugin(name, *args, **kwargs)
        plugins_dict[name] = plugin

    return {
        "register": plugin_register,
        "runtime": runtime,
    }


# TODO: Stop taking this argument. Plugins shouldn't be in-process.
def load_plugins(runtime):
    plugins_dict = {}
    for _, name, _ in pkgutil.iter_modules(plugins.__path__):
        plugin_module = __import__(plugins.__name__ + "." + name,
                                   fromlist="dummy")
        entry_point = plugin_module.peru_plugin_main
        entry_point(**_entry_point_kwargs(runtime, plugins_dict))

    return plugins_dict


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

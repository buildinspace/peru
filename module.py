import module
import rule
import plugin

class ToplevelModule:
    field_names = {"import"}

    def __init__(self, d):
        self.fields = {}
        self.children = {}
        for name, val in d.items():
            parts = key.split()
            if len(parts) > 2 or len(parts) == 0:
                raise RuntimeError('bad field "{}"'.format(name))
            elif len(parts) == 1:
                if name not in self.field_names:
                    raise RuntimeError('unknown field "{}"'.format(name))
                fields[name] = val
            else:
                type_, name = parts
                self._add_child(type_, name, val)

    def _add_child(type_, name, val):
        if name in self.children:
            raise RuntimeError('"{}" already defined'.format(name))
        if type_ == "rule":
            self.children[name] = rule.Rule(name, val)
        elif type_ == "module":
            self.children[name] = RemoteModule(name, val)
        else:
            raise RuntimeError('unknown type "{}"'.format(type_))

    def build(path):
        #TODO: deps
        if "default" in self.fields:
            return self.fields["default"].build(path)
        else:
            return Rule(self, {}).build(path)



class RemoteModule:
    def __init__(self, name, d):
        self.name = name
        if "type" not in d:
            raise RuntimeError('module "{}" must have a "type" field'
                               .format(name))
        self.plugin = plugin.get(d["type"])
        plugin_fields = {key: val for key, val in d.items()
                         if key in plugin.field_names}
        rest = {key: val for key, val in d.itemd()
                if key not in plugin.field_names and key != "type"}
        for key in rest:
            if key not in ToplevelModule.field_names:
                raise RuntimeError('unknown field "{}"'.format(key))


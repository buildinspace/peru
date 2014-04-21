import re
import yaml

from .local_module import LocalModule
from .remote_module import RemoteModule
from .rule import Rule


class Parser:
    def __init__(self, plugins):
        self.plugins = plugins

    def parse_file(self, path):
        with open(path) as f:
            return self.parse_string(f.read())

    def parse_string(self, yaml_str):
        blob = yaml.safe_load(yaml_str)
        local_module = self._build_local_module(blob)
        return local_module

    def _extract_rules(self, blob):
        rules = {}
        for field in list(blob.keys()):
            parts = field.split()
            if len(parts) == 2 and parts[0] == "rule":
                inner_blob = blob.pop(field)  # remove the field from blob
                name = parts[1]
                rules[name] = self._build_rule(name, inner_blob)
        return rules

    def _extract_modules(self, blob):
        scope = {}
        for field in list(blob.keys()):
            parts = field.split()
            if len(parts) == 3 and parts[1] == "module":
                type, _, name = parts
                inner_blob = blob.pop(field)  # remove the field from blob
                rules = self._extract_rules(inner_blob)
                module = self._build_remote_module(name, type, inner_blob)
                module_scope = {name: module}
                _add_to_scope(module_scope, rules, prefix=name + ".")
                _add_to_scope(scope, module_scope)
        return scope

    def _build_remote_module(self, name, type, blob):
        if type not in self.plugins:
            raise RuntimeError("Unknown module type: " + type)
        plugin = self.plugins[type]
        plugin_fields = plugin.extract_fields(blob, name)
        imports = blob.pop("imports", {})
        module = RemoteModule(
            name, imports, plugin, plugin_fields)
        if blob:
            raise RuntimeError("Unknown module fields: " +
                               ", ".join(blob.keys()))
        return module

    def _build_rule(self, name, blob):
        _validate_name(name)
        if blob is None:
            # Rules can be totally empty, which makes them a no-op.
            blob = {}
        rule = Rule(name,
                    blob.pop("imports", {}),
                    blob.pop("build", None),
                    blob.pop("export", None))
        if blob:
            raise RuntimeError("Unknown rule fields: " +
                               ", ".join(blob.keys()))
        return rule

    def _build_local_module(self, blob):
        scope = {}
        rules = self._extract_rules(blob)
        _add_to_scope(scope, rules)
        modules = self._extract_modules(blob)
        _add_to_scope(scope, modules)
        imports = blob.pop("imports", {})
        local_module = LocalModule(scope, imports)
        if blob:
            raise RuntimeError("Unknown toplevel fields: " +
                               ", ".join(blob.keys()))
        return local_module


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise RuntimeError("Invalid name: " + repr(name))
    return name


def _add_to_scope(scope, new_items, prefix=""):
    prefixed_items = {prefix + key: val for key, val in new_items.items()}
    for key in prefixed_items:
        if key in scope:
            raise RuntimeError(key + " is defined more than once.")
    scope.update(prefixed_items)

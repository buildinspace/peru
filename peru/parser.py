import re
import yaml

from .local_module import LocalModule
from .remote_module import RemoteModule
from .rule import Rule


class ParserError(RuntimeError):
    def __init__(self, *args):
        RuntimeError.__init__(self, *args)


def parse_file(path):
    with open(path) as f:
        return parse_string(f.read())


def parse_string(yaml_str):
    blob = yaml.safe_load(yaml_str)
    if blob is None:
        blob = {}
    return _parse_toplevel(blob)


def _extract_rules(blob):
    rules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            name = parts[1]
            rules[name] = _build_rule(name, inner_blob)
    return rules


def _extract_modules(blob):
    scope = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 3 and parts[1] == "module":
            type, _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            rules = _extract_rules(inner_blob)
            module = _build_remote_module(name, type, inner_blob)
            module_scope = {name: module}
            _add_to_scope(module_scope, rules, prefix=name + ".")
            _add_to_scope(scope, module_scope)
    return scope


def _build_remote_module(name, type, blob):
    imports = blob.pop("imports", {})
    module = RemoteModule(name, type, imports, plugin_fields=blob)
    return module


def _build_rule(name, blob):
    _validate_name(name)
    if blob is None:
        # Rules can be totally empty, which makes them a no-op.
        blob = {}
    rule = Rule(name,
                blob.pop("build", None),
                blob.pop("export", None))
    if blob:
        raise ParserError("Unknown rule fields: " + ", ".join(blob.keys()))
    return rule


def _build_local_module(blob):
    imports = blob.pop("imports", {})
    if blob:
        raise ParserError("Unknown toplevel fields: " +
                          ", ".join(blob.keys()))
    return LocalModule(imports)


def _parse_toplevel(blob):
    scope = {}
    rules = _extract_rules(blob)
    _add_to_scope(scope, rules)
    modules = _extract_modules(blob)
    _add_to_scope(scope, modules)
    local_module = _build_local_module(blob)
    return (scope, local_module)


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise ParserError("Invalid name: " + repr(name))
    return name


def _add_to_scope(scope, new_items, prefix=""):
    prefixed_items = {prefix + key: val for key, val in new_items.items()}
    for key in prefixed_items:
        if key in scope:
            raise ParserError(key + " is defined more than once.")
    scope.update(prefixed_items)

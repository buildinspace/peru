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


def _parse_toplevel(blob):
    scope = {}
    _extract_rules(blob, scope)
    _extract_modules(blob, scope)
    local_module = _build_local_module(blob)
    return (scope, local_module)


def _extract_rules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            rule = _build_rule(name, inner_blob)
            _add_to_scope(scope, name, rule)


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


def _extract_modules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 3 and parts[1] == "module":
            type, _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            module = _build_remote_module(name, type, inner_blob)
            _add_to_scope(scope, name, module)


def _build_remote_module(name, type, blob):
    imports = blob.pop("imports", {})
    default_rule = _extract_default_rule(blob)
    module = RemoteModule(name, type, imports, default_rule, blob)
    return module


def _build_local_module(blob):
    imports = blob.pop("imports", {})
    default_rule = _extract_default_rule(blob)
    if blob:
        raise ParserError("Unknown toplevel fields: " +
                          ", ".join(blob.keys()))
    return LocalModule(imports, default_rule)


def _extract_default_rule(blob):
    if "rule" not in blob:
        return None
    rule_blob = blob.pop("rule")
    rule = _build_rule("<default>", rule_blob)
    return rule


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise ParserError("Invalid name: " + repr(name))
    return name


def _add_to_scope(scope, name, obj):
    if name in scope:
        raise ParserError('"{}" is defined more than once'.format(name))
    scope[name] = obj

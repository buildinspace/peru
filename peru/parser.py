import os
import re
import yaml

from .error import PrintableError
from .local_module import LocalModule
from .remote_module import RemoteModule
from .rule import Rule


class ParserError(PrintableError):
    pass


def parse_file(file_path, **local_module_kwargs):
    project_root = os.path.dirname(file_path)
    with open(file_path) as f:
        return parse_string(f.read(), project_root, **local_module_kwargs)


def parse_string(yaml_str, project_root='.', **local_module_kwargs):
    try:
        blob = yaml.safe_load(yaml_str)
    except yaml.scanner.ScannerError as e:
        raise PrintableError("YAML parser error:\n\n" + str(e)) from e
    if blob is None:
        blob = {}
    return _parse_toplevel(blob, root=project_root, **local_module_kwargs)


def _parse_toplevel(blob, **local_module_kwargs):
    scope = {}
    _extract_named_rules(blob, scope)
    _extract_remote_modules(blob, scope)
    local_module = _build_local_module(blob, **local_module_kwargs)
    return (scope, local_module)


def _build_local_module(blob, **local_module_kwargs):
    imports = blob.pop("imports", {})
    default_rule = _extract_default_rule(blob)
    if blob:
        raise ParserError("Unknown toplevel fields: " +
                          ", ".join(blob.keys()))
    return LocalModule(imports, default_rule, **local_module_kwargs)


def _extract_named_rules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            rule = _extract_rule(name, inner_blob)
            if inner_blob:
                raise ParserError("Unknown rule fields: " +
                                  ", ".join(inner_blob.keys()))
            _add_to_scope(scope, name, rule)


def _extract_rule(name, blob):
    _validate_name(name)
    build_command = blob.pop("build", None)
    export = blob.pop("export", None)
    if build_command is None and export is None:
        return None
    rule = Rule(name, build_command, export)
    return rule


def _extract_default_rule(blob):
    return _extract_rule("<default>", blob)


def _extract_remote_modules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 3 and parts[1] == "module":
            type, _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            yaml_name = field
            module = _build_remote_module(name, type, inner_blob, yaml_name)
            _add_to_scope(scope, name, module)


def _build_remote_module(name, type, blob, yaml_name):
    _validate_name(name)
    imports = blob.pop("imports", {})
    default_rule = _extract_default_rule(blob)
    plugin_fields = blob
    assert all(isinstance(val, str) for val in plugin_fields.values()), \
        "all plugin fields must be strings"
    assert all(not re.findall("\s", name) for name in plugin_fields), \
        "whitespace is not allowed in plugin field names"
    module = RemoteModule(name, type, imports, default_rule, plugin_fields,
                          yaml_name)
    return module


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise ParserError("Invalid name: " + repr(name))
    return name


def _add_to_scope(scope, name, obj):
    if name in scope:
        raise ParserError('"{}" is defined more than once'.format(name))
    scope[name] = obj

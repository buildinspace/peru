import collections
import os
import re
import yaml

from .error import PrintableError
from .local_module import LocalModule
from .remote_module import RemoteModule
from .rule import Rule


class ParserError(PrintableError):
    pass


ParseResult = collections.namedtuple(
    "ParseResult", ["scope", "local_module"])


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
    return ParseResult(scope, local_module)


def _build_local_module(blob, **local_module_kwargs):
    imports = _extract_imports(blob)
    default_rule = _extract_default_rule(blob)
    if blob:
        raise ParserError("Unknown toplevel fields: " +
                          ", ".join(blob.keys()))
    return LocalModule(imports, default_rule, **local_module_kwargs)


def _extract_named_rules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split(' ')
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
    build_command = blob.pop('build', None)
    export = blob.pop('export', None)
    files = _extract_maybe_list_field(blob, 'files')
    if not build_command and not export and not files:
        return None
    rule = Rule(name, build_command, export, files)
    return rule


def _extract_default_rule(blob):
    return _extract_rule("<default>", blob)


def _extract_remote_modules(blob, scope):
    for field in list(blob.keys()):
        parts = field.split(' ')
        if len(parts) == 3 and parts[1] == "module":
            type, _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            yaml_name = field
            module = _build_remote_module(name, type, inner_blob, yaml_name)
            _add_to_scope(scope, name, module)


def _build_remote_module(name, type, blob, yaml_name):
    _validate_name(name)
    default_rule = _extract_default_rule(blob)
    plugin_fields = blob

    # Do some validation on the module fields.
    non_string_fields = [(key, val) for key, val in plugin_fields.items()
                         if not isinstance(key, str)
                         or not isinstance(val, str)]
    if non_string_fields:
        raise ParserError(
            'Module field names and values must be strings: ' +
            ', '.join(repr(pair) for pair in non_string_fields))

    module = RemoteModule(name, type, default_rule, plugin_fields, yaml_name)
    return module


# Module imports can come from a dictionary or a list (of key-val pairs), and
# the Imports struct is here to hide that from other code. `pairs` is a list of
# target-path tuples, which could contain the same target or path more than
# once. `targets` is a list of targets with no duplicates. Both should have a
# deterministic order, which is the same as the original list order if the
# imports came from a list (modulo removing duplicates from `targets`).
Imports = collections.namedtuple('Imports', ['targets', 'pairs'])


def build_imports(dict_or_list):
    '''Imports can be a map:
        imports:
            a: path/
            b: path/
    Or a list (to allow duplicate keys):
        imports
            - a: path/
            - b: path/
    We need to parse both.'''
    if isinstance(dict_or_list, dict):
        return _imports_from_dict(dict_or_list)
    elif isinstance(dict_or_list, list):
        return _imports_from_list(dict_or_list)
    elif dict_or_list is None:
        return Imports((), ())
    else:
        raise ParserError(
            'Imports must be a map or a list of key-value pairs.')


def _imports_from_dict(imports_dict):
    # We need to make sure the sort order is deterministic.
    targets = tuple(sorted(imports_dict.keys()))
    return Imports(
        targets,
        tuple((target, imports_dict[target]) for target in targets))


def _imports_from_list(imports_list):
    # We need to keep the given sort order, but discard duplicates from the
    # list of targets.
    targets = []
    pairs = []
    for pair in imports_list:
        if not isinstance(pair, dict) or len(pair) != 1:
            raise ParserError(
                'Elements of an imports list must be key-value pairs.')
        target, path = list(pair.items())[0]
        # Build up the list of unique targets. Note that this is a string
        # comparison. If it ever becomes possible to write the same target in
        # more than one way (like with flexible whitespace), we will need to
        # canonicalize these strings.
        if target not in targets:
            targets.append(target)
        pairs.append((target, path))
    return Imports(tuple(targets), tuple(pairs))


def _extract_imports(blob):
    importsblob = blob.pop('imports', {})
    return build_imports(importsblob)


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise ParserError("Invalid name: " + repr(name))
    return name


def _add_to_scope(scope, name, obj):
    if name in scope:
        raise ParserError('"{}" is defined more than once'.format(name))
    scope[name] = obj


def _extract_maybe_list_field(blob, name):
    '''Handle optional fields that can be either a string or a list of
    strings.'''
    raw_value = blob.pop(name, [])
    if isinstance(raw_value, str):
        value = (raw_value,)
    elif isinstance(raw_value, list):
        value = tuple(raw_value)
    else:
        raise ParserError('"{}" field must be a string or a list.'
                          .format(name))
    return value

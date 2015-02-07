import collections
import re
import sys
import textwrap
import yaml

from .error import PrintableError
from .module import Module
from .rule import Rule
from .scope import Scope


DEFAULT_PERU_FILE_NAME = 'peru.yaml'


class ParserError(PrintableError):
    pass


def parse_file(file_path, name_prefix=""):
    with open(file_path) as f:
        return parse_string(f.read(), name_prefix)


def parse_string(yaml_str, name_prefix=""):
    try:
        blob = yaml.safe_load(yaml_str)
    except yaml.scanner.ScannerError as e:
        raise PrintableError("YAML parser error:\n\n" + str(e)) from e
    if blob is None:
        blob = {}
    return _parse_toplevel(blob, name_prefix)


def _parse_toplevel(blob, name_prefix):
    modules = _extract_modules(blob, name_prefix)
    rules = _extract_named_rules(blob, name_prefix)
    imports = _extract_imports(blob)
    if blob:
        raise ParserError("Unknown toplevel fields: " +
                          ", ".join(blob.keys()))
    return Scope(modules, rules), imports


def _extract_named_rules(blob, name_prefix):
    scope = {}
    for field in list(blob.keys()):
        parts = field.split(' ')
        if len(parts) == 2 and parts[0] == "rule":
            _, name = parts
            if name in scope:
                raise ParserError('Rule "{}" already exists.'.format(name))
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            rule = _extract_rule(name_prefix + name, inner_blob)
            if inner_blob:
                raise ParserError("Unknown rule fields: " +
                                  ", ".join(inner_blob.keys()))
            scope[name] = rule
    return scope


def _extract_rule(name, blob):
    _validate_name(name)
    if 'build' in blob:
        raise ParserError(textwrap.dedent('''\
            The "build" field is no longer supported. If you need to
            untar/unzip a curl module, use the "unpack" field.'''))
    export = blob.pop('export', None)
    # TODO: Remove the `files` field. Until this is done, print a deprecation
    # message.
    files = _extract_maybe_list_field(blob, 'files')
    if files:
        print('Warning: The `files` field is deprecated. Use `pick` instead.',
              file=sys.stderr)
    pick = _extract_maybe_list_field(blob, 'pick')
    executable = _extract_maybe_list_field(blob, 'executable')
    if not export and not files and not pick and not executable:
        return None
    rule = Rule(name, export, files, pick, executable)
    return rule


def _extract_default_rule(blob):
    return _extract_rule("<default>", blob)


def _extract_modules(blob, name_prefix):
    scope = {}
    for field in list(blob.keys()):
        parts = field.split(' ')
        if len(parts) == 3 and parts[1] == 'module':
            type, _, name = parts
            _validate_name(name)
            if name in scope:
                raise ParserError('Module "{}" already exists.'.format(name))
            inner_blob = blob.pop(field)  # remove the field from blob
            inner_blob = {} if inner_blob is None else inner_blob
            yaml_name = field
            module = _build_module(name_prefix + name, type, inner_blob,
                                   yaml_name)
            scope[name] = module
    return scope


def _build_module(name, type, blob, yaml_name):
    peru_file = blob.pop('peru file', DEFAULT_PERU_FILE_NAME)
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

    module = Module(name, type, default_rule, plugin_fields, yaml_name,
                    peru_file)
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

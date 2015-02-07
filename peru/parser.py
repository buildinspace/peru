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


def build_imports(multimap):
    '''Import values can be a scalar or a list:
        imports:
          a: foo/
          b:
            - bar/
            - baz/
    We need to parse both.'''
    message = ('Imports must be a map whose values are either a string or '
               'list of strings.')
    # We use an `OrderedDict` here to ensure that imports happen in determinist
    # order. This prevents obscure bugs caused by imports occuring differently
    # at different times.
    imports = collections.OrderedDict()
    if not multimap:
        return imports
    elif not isinstance(multimap, dict):
        raise ParserError(message)
    # Sort by key so that imports occur in convenient lexographical order. This
    # keeps things deterministic in a simple way.
    for target, value in sorted(multimap.items()):
        paths = _optional_list(value)
        if paths is None:
            raise ParserError(message)
        imports[target] = paths  # Remembers order.
    return imports


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
    value = _optional_list(blob.pop(name, []))
    if value is None:
        raise ParserError('"{}" field must be a string or a list.'
                          .format(name))
    return value


def _optional_list(value):
    '''Convert a value that may be a scalar (str) or list into a tuple. This
    produces uniform output for fields that may supply a single value or list
    of values, like the `imports` field.'''
    if isinstance(value, str):
        return (value,)
    elif isinstance(value, list):
        return tuple(value)

    return None  # Let callers raise errors.

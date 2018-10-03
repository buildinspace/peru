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
    imports = _extract_multimap_field(blob, 'imports')
    if blob:
        raise ParserError("Unknown toplevel fields: " + ", ".join(blob.keys()))
    return Scope(modules, rules), imports


def _extract_named_rules(blob, name_prefix):
    scope = {}
    for field in list(blob.keys()):
        parts = field.split(' ')
        if len(parts) == 2 and parts[0] == "rule":
            _, name = parts
            if name in scope:
                raise ParserError('Rule "{}" already exists.'.format(name))
            inner_blob = typesafe_pop(blob, field)
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
        raise ParserError(
            textwrap.dedent('''\
            The "build" field is no longer supported. If you need to
            untar/unzip a curl module, use the "unpack" field.'''))
    if 'files' in blob:
        raise ParserError(
            'The "files" field is no longer supported. Use "pick" instead.')
    copy = _extract_multimap_field(blob, 'copy')
    move = _extract_multimap_field(blob, 'move')
    executable = _extract_optional_list_field(blob, 'executable')
    drop = _extract_optional_list_field(blob, 'drop')
    pick = _extract_optional_list_field(blob, 'pick')
    export = typesafe_pop(blob, 'export', None)
    if not any((copy, move, executable, drop, pick, export)):
        return None
    rule = Rule(name, copy, move, executable, drop, pick, export)
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
            inner_blob = typesafe_pop(blob, field)
            inner_blob = {} if inner_blob is None else inner_blob
            yaml_name = field
            module = _build_module(name_prefix + name, type, inner_blob,
                                   yaml_name)
            scope[name] = module
    return scope


def _build_module(name, type, blob, yaml_name):
    peru_file = typesafe_pop(blob, 'peru file', DEFAULT_PERU_FILE_NAME)
    recursive = typesafe_pop(blob, 'recursive', None)
    default_rule = _extract_default_rule(blob)
    plugin_fields = blob

    # Stringify all the plugin fields.
    for k, v in plugin_fields.items():
        if not isinstance(k, str):
            raise ParserError(
                'Module field names must be strings. Found "{}".'.format(
                    repr(k)))
        if isinstance(v, bool):
            # Avoid the Python-specific True/False capitalization, to be
            # consistent with what people will usually type in YAML.
            plugin_fields[k] = "true" if v else "false"
        else:
            plugin_fields[k] = str(v)

    module = Module(name, type, default_rule, plugin_fields, yaml_name,
                    peru_file, recursive)
    return module


def _validate_name(name):
    if re.search(r"[\s:.]", name):
        raise ParserError("Invalid name: " + repr(name))
    return name


def _extract_optional_list_field(blob, name):
    '''Handle optional fields that can be either a string or a list of
    strings.'''
    value = _optional_list(typesafe_pop(blob, name, []))
    if value is None:
        raise ParserError(
            '"{}" field must be a string or a list.'.format(name))
    return value


def _extract_multimap_field(blob, name):
    '''Extracts multimap fields. Values can either be a scalar string or a list
    of strings. We need to parse both. For example:
        example:
          a: foo/
          b:
            - bar/
            - baz/'''
    message = ('"{}" field must be a map whose values are either a string or '
               'list of strings.'.format(name))
    raw_map = typesafe_pop(blob, name, {}) or {}
    if not isinstance(raw_map, dict):
        raise ParserError(message)
    # We use an `OrderedDict` to ensure that multimap fields are processed in a
    # determinist order. This prevents obscure bugs caused by subtly different
    # behavior.
    multimap = collections.OrderedDict()
    # Sort by key so that processing occurs in convenient lexographical order.
    # This keeps things deterministic in a simple way.
    for key, raw_value in sorted(raw_map.items()):
        value = _optional_list(raw_value)
        if value is None:
            raise ParserError(message)
        multimap[key] = value  # Remembers order.
    return multimap


def _optional_list(value):
    '''Convert a value that may be a scalar (str) or list into a tuple. This
    produces uniform output for fields that may supply a single value or list
    of values, like the `imports` field.'''
    if isinstance(value, str):
        return (value, )
    elif isinstance(value, list):
        return tuple(value)

    return None  # Let callers raise errors.


def typesafe_pop(d, field, default=object()):
    if not isinstance(d, dict):
        raise ParserError('Error parsing peru file: {} is not a map.'.format(
            repr(d)))
    if default == typesafe_pop.__defaults__[0]:
        return d.pop(field)
    else:
        return d.pop(field, default)


# Code for the duplicate keys warning

DuplicatedKey = collections.namedtuple('DuplicatedKey',
                                       ['key', 'first_line', 'second_line'])


def _get_line_indentation(line):
    indentation = 0
    for c in line:
        # YAML forbids tabs, so we only need to look for spaces.
        if c == ' ':
            indentation += 1
        else:
            return indentation


def _get_duplicate_keys_approximate(yaml_text):
    duplicates = []
    lines = yaml_text.split('\n')
    # Keep track of the keys that we've found, and the lines where we found
    # them, for every indentation level we've encountered.
    indent_to_keylines = collections.defaultdict(dict)
    for _line_index, line in enumerate(lines):
        line_num = _line_index + 1
        # Strip comments. This (and several other steps below) will do the
        # wrong thing for quoted keys that happen to contain the '#' character
        # in them, but since this is just for the sake of a warning, we don't
        # want to add all the code that would be needed to deal with it.
        if '#' in line:
            line = line[:line.index('#')]
        # Ignore lines that are not dictionary keys.
        if ':' not in line:
            continue
        current_indent = _get_line_indentation(line)
        # When an indented block ends, forget all the keys that were in it.
        for indent in list(indent_to_keylines.keys()):
            if indent > current_indent:
                del indent_to_keylines[indent]
        # Check if the current key is a duplicate.
        key = line.split(':')[0].strip()
        if key in indent_to_keylines[current_indent]:
            duplicates.append(
                DuplicatedKey(key, indent_to_keylines[current_indent][key],
                              line_num))
        # Remember it either way.
        indent_to_keylines[current_indent][key] = line_num
    return duplicates


def _warn(s, *args, **kwargs):
    print(s.format(*args, **kwargs), file=sys.stderr)


def warn_duplicate_keys(file_path):
    with open(file_path) as f:
        text = f.read()
    duplicates = _get_duplicate_keys_approximate(text)
    if not duplicates:
        return
    _warn(
        'WARNING: Duplicate keys found in {}\n'
        'These will overwrite each other:', file_path)
    for duplicate in duplicates:
        _warn('  "{}" on lines {} and {}', *duplicate)

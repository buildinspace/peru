from textwrap import dedent
import unittest

from peru.parser import parse_string, ParserError, build_imports
from peru.module import Module
from peru.rule import Rule


class ParserTest(unittest.TestCase):

    def test_parse_empty_file(self):
        result = parse_string('')
        self.assertDictEqual(result.modules, {})
        self.assertDictEqual(result.rules, {})
        self.assertEqual(result.imports, build_imports({}))

    def test_parse_rule(self):
        input = dedent("""\
            rule foo:
                export: out/
            """)
        result = parse_string(input)
        self.assertIn("foo", result.rules)
        rule = result.rules["foo"]
        self.assertIsInstance(rule, Rule)
        self.assertEqual(rule.name, "foo")
        self.assertEqual(rule.export, "out/")

    def test_parse_module(self):
        input = dedent("""\
            sometype module foo:
                url: http://www.example.com/
                rev: abcdefg
            """)
        result = parse_string(input)
        self.assertIn("foo", result.modules)
        module = result.modules["foo"]
        self.assertIsInstance(module, Module)
        self.assertEqual(module.name, "foo")
        self.assertEqual(module.type, "sometype")
        self.assertDictEqual(module.plugin_fields,
                             {"url": "http://www.example.com/",
                              "rev": "abcdefg"})

    def test_parse_module_default_rule(self):
        input = dedent("""\
            git module bar:
                export: bar
            """)
        result = parse_string(input)
        self.assertIn("bar", result.modules)
        module = result.modules["bar"]
        self.assertIsInstance(module, Module)
        self.assertIsInstance(module.default_rule, Rule)
        self.assertEqual(module.default_rule.export, "bar")

    def test_parse_toplevel_imports(self):
        input = dedent("""\
            imports:
                foo: bar/
            """)
        result = parse_string(input)
        self.assertDictEqual(result.modules, {})
        self.assertDictEqual(result.rules, {})
        self.assertEqual(result.imports, build_imports({'foo': 'bar/'}))

    def test_parse_list_imports(self):
        input = dedent('''\
            imports:
                - foo: bar/
            ''')
        result = parse_string(input)
        self.assertDictEqual(result.modules, {})
        self.assertDictEqual(result.rules, {})
        self.assertEqual(result.imports, build_imports({'foo': 'bar/'}))

    def test_parse_empty_imports(self):
        input = dedent('''\
            imports:
            ''')
        result = parse_string(input)
        self.assertDictEqual(result.modules, {})
        self.assertDictEqual(result.rules, {})
        self.assertEqual(result.imports, build_imports({}))

    def test_parse_wrong_type_imports_throw(self):
        with self.assertRaises(ParserError):
            parse_string('imports: 5')

    def test_parse_bad_list_imports_throw(self):
        input = dedent('''\
            imports:
                - a: foo
                  b: bar
        ''')
        with self.assertRaises(ParserError):
            parse_string(input)

    def test_bad_toplevel_field_throw(self):
        with self.assertRaises(ParserError):
            parse_string("foo: bar")

    def test_bad_rule_field_throw(self):
        with self.assertRaises(ParserError):
            parse_string(dedent("""\
                rule foo:
                    bad_field: junk
                """))

    def test_bad_rule_name_throw(self):
        with self.assertRaises(ParserError):
            parse_string("rule foo bar:")

    def test_bad_module_name_throw(self):
        with self.assertRaises(ParserError):
            parse_string("git module abc def:")
        with self.assertRaises(ParserError):
            parse_string("git module:")

    def test_duplicate_names_throw(self):
        # Modules and rules should not conflict.
        ok_input = dedent('''
            rule foo:
            git module foo:
            ''')
        parse_string(ok_input)
        # But duplicate modules should fail. (Duplicate rules are a not
        # currently possible, because their YAML keys would be exact
        # duplicates.)
        bad_input = dedent('''
            git module foo:
            hg module foo:
            ''')
        with self.assertRaises(ParserError):
            parse_string(bad_input)

    def test_non_string_module_field_name(self):
        input = dedent('''\
            git module foo:
                12345: bar
            ''')
        try:
            parse_string(input)
        except ParserError as e:
            assert '12345' in e.message
        else:
            assert False, 'expected ParserError'

    def test_non_string_module_field_value(self):
        input = dedent('''\
            git module foo:
                bar: 4567
            ''')
        try:
            parse_string(input)
        except ParserError as e:
            assert '4567' in e.message
        else:
            assert False, 'expected ParserError'

    def test_build_field_deprecated_message(self):
        input = dedent('''\
            rule foo:
                build: shell command
            ''')
        try:
            parse_string(input)
        except ParserError as e:
            assert 'The "build" field is no longer supported.' in e.message
        else:
            assert False, 'expected ParserError'

from textwrap import dedent
import unittest

from peru.parser import build_imports, parse_string, ParserError
from peru.remote_module import RemoteModule
from peru.rule import Rule

import shared


class ParserTest(unittest.TestCase):

    def test_parse_empty_file(self):
        result = parse_string('')
        self.assertDictEqual(result.scope, {})
        self.assertEqual(result.local_module.imports, build_imports({}))
        self.assertEqual(result.local_module.default_rule, None)
        self.assertEqual(result.local_module.root, '.')

    def test_parse_with_project_root(self):
        project_root = shared.create_dir()
        result = parse_string('', project_root=project_root)
        self.assertEqual(result.local_module.root, project_root)

    def test_parse_rule(self):
        input = dedent("""\
            rule foo:
                build: echo hi
                export: out/
            """)
        result = parse_string(input)
        self.assertIn("foo", result.scope)
        rule = result.scope["foo"]
        self.assertIsInstance(rule, Rule)
        self.assertEqual(rule.name, "foo")
        self.assertEqual(rule.build_command, "echo hi")
        self.assertEqual(rule.export, "out/")

    def test_parse_module(self):
        input = dedent("""\
            sometype module foo:
                url: http://www.example.com/
                rev: abcdefg
            """)
        result = parse_string(input)
        self.assertIn("foo", result.scope)
        module = result.scope["foo"]
        self.assertIsInstance(module, RemoteModule)
        self.assertEqual(module.name, "foo")
        self.assertEqual(module.type, "sometype")
        self.assertDictEqual(module.plugin_fields,
                             {"url": "http://www.example.com/",
                              "rev": "abcdefg"})

    def test_parse_module_default_rule(self):
        input = dedent("""\
            git module bar:
                build: foo
                export: bar
            """)
        result = parse_string(input)
        self.assertIn("bar", result.scope)
        module = result.scope["bar"]
        self.assertIsInstance(module, RemoteModule)
        self.assertIsInstance(module.default_rule, Rule)
        self.assertEqual(module.default_rule.build_command, "foo")
        self.assertEqual(module.default_rule.export, "bar")

    def test_parse_toplevel_imports(self):
        input = dedent("""\
            imports:
                foo: bar/
            """)
        result = parse_string(input)
        self.assertDictEqual(result.scope, {})
        self.assertEqual(result.local_module.imports, build_imports(
            {'foo': 'bar/'}))

    def test_parse_list_imports(self):
        input = dedent('''\
            imports:
                - foo: bar/
            ''')
        result = parse_string(input)
        self.assertDictEqual(result.scope, {})
        self.assertEqual(result.local_module.imports, build_imports(
            {'foo': 'bar/'}))

    def test_parse_empty_imports(self):
        input = dedent('''\
            imports:
            ''')
        result = parse_string(input)
        self.assertDictEqual(result.scope, {})
        self.assertEqual(result.local_module.imports, build_imports({}))

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
        input = dedent("""
            git module {}:
            rule {}:
            """)
        # Should be fine with different names...
        parse_string(input.format("foo", "bar"))
        # But should fail with duplicates.
        with self.assertRaises(ParserError):
            parse_string(input.format("foo", "foo"))

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

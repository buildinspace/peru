from textwrap import dedent
import unittest

from peru.parser import parse_string, ParserError
from peru.remote_module import RemoteModule
from peru.rule import Rule

import shared


class ParserTest(unittest.TestCase):

    def test_parse_empty_file(self):
        result = parse_string('')
        self.assertDictEqual(result.scope, {})
        self.assertDictEqual(result.local_module.imports, {})
        self.assertEqual(result.local_module.default_rule, None)
        self.assertEqual(result.local_module.root, '.')
        self.assertTupleEqual(result.plugin_paths, ())

    def test_parse_with_project_root(self):
        project_root = shared.create_dir()
        result = parse_string('', project_root=project_root)
        self.assertEqual(result.local_module.root, project_root)

    def test_parse_with_plugin_paths(self):
        result = parse_string(dedent('''\
            plugins: foo
            '''))
        self.assertTupleEqual(('foo',), result.plugin_paths)

    def test_parse_with_list_of_plugin_paths(self):
        result = parse_string(dedent('''\
            plugins:
              - foo
              - bar
            '''))
        self.assertTupleEqual(('foo', 'bar'), result.plugin_paths)

    def test_parse_with_bad_plugin_paths(self):
        wrong_type = dedent('''\
            plugins: 5
            ''')
        with self.assertRaises(ParserError):
            parse_string(wrong_type)
        empty_val = dedent('''\
            plugins:
            ''')
        with self.assertRaises(ParserError):
            parse_string(empty_val)

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
                imports:
                    wham: bam/
                    thank: you/maam
            """)
        result = parse_string(input)
        self.assertIn("foo", result.scope)
        module = result.scope["foo"]
        self.assertIsInstance(module, RemoteModule)
        self.assertEqual(module.name, "foo")
        self.assertEqual(module.type, "sometype")
        self.assertDictEqual(module.imports,
                             {"wham": "bam/",
                              "thank": "you/maam"})
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
        self.assertDictEqual(result.local_module.imports, {"foo": "bar/"})

    def test_parse_empty_imports(self):
        input = dedent('''\
            imports:
            ''')
        result = parse_string(input)
        self.assertDictEqual(result.scope, {})
        self.assertDictEqual(result.local_module.imports, {})

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

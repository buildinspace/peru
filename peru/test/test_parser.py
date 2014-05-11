from textwrap import dedent
import unittest

from peru.parser import parse_string, ParserError
from peru.remote_module import RemoteModule
from peru.rule import Rule


class ParserTest(unittest.TestCase):

    def test_parse_empty_file(self):
        scope, local_module = parse_string("")
        self.assertDictEqual(scope, {})
        self.assertDictEqual(local_module.imports, {})

    def test_parse_rule(self):
        input = dedent("""\
            rule foo:
                build: echo hi
                export: out/
            """)
        scope, local_module = parse_string(input)
        self.assertIn("foo", scope)
        rule = scope["foo"]
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
        scope, local_module = parse_string(input)
        self.assertIn("foo", scope)
        module = scope["foo"]
        self.assertIsInstance(module, RemoteModule)
        self.assertEqual(module.name, "foo")
        self.assertEqual(module.type, "sometype")
        self.assertDictEqual(module.imports,
                             {"wham": "bam/",
                              "thank": "you/maam"})
        self.assertDictEqual(module.plugin_fields,
                             {"url": "http://www.example.com/",
                              "rev": "abcdefg"})

    def test_parse_nested_rule(self):
        input = dedent("""\
            git module bar:
                rule baz:
            """)
        scope, local_module = parse_string(input)
        self.assertIn("bar", scope)
        module = scope["bar"]
        self.assertIsInstance(module, RemoteModule)
        self.assertIn("bar.baz", scope)
        rule = scope["bar.baz"]
        self.assertIsInstance(rule, Rule)

    def test_parse_toplevel_imports(self):
        input = dedent("""\
            imports:
                foo: bar/
            """)
        scope, local_module = parse_string(input)
        self.assertDictEqual(scope, {})
        self.assertDictEqual(local_module.imports, {"foo": "bar/"})

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
        with self.assertRaises(ParserError):
            parse_string("rule:")

    def test_bad_module_name_throw(self):
        with self.assertRaises(ParserError):
            parse_string("git module abc def:")
        with self.assertRaises(ParserError):
            parse_string("git module:")

from textwrap import dedent
import unittest

from peru.parser import parse_string
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
            git module foo:
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
        self.assertDictEqual(module.imports,
                             {"wham": "bam/",
                              "thank": "you/maam"})
        self.assertDictEqual(module.plugin_fields,
                             {"url": "http://www.example.com/",
                              "rev": "abcdefg"})

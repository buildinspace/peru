from textwrap import dedent

from peru import parser
from peru.parser import parse_string, ParserError
from peru.module import Module
from peru.rule import Rule
import shared


class ParserTest(shared.PeruTest):
    def test_parse_empty_file(self):
        scope, imports = parse_string('')
        self.assertDictEqual(scope.modules, {})
        self.assertDictEqual(scope.rules, {})
        self.assertEqual(imports, {})

    def test_parse_rule(self):
        input = dedent("""\
            rule foo:
                export: out/
            """)
        scope, imports = parse_string(input)
        self.assertIn("foo", scope.rules)
        rule = scope.rules["foo"]
        self.assertIsInstance(rule, Rule)
        self.assertEqual(rule.name, "foo")
        self.assertEqual(rule.export, "out/")

    def test_parse_module(self):
        input = dedent("""\
            sometype module foo:
                url: http://www.example.com/
                rev: abcdefg
            """)
        scope, imports = parse_string(input)
        self.assertIn("foo", scope.modules)
        module = scope.modules["foo"]
        self.assertIsInstance(module, Module)
        self.assertEqual(module.name, "foo")
        self.assertEqual(module.type, "sometype")
        self.assertDictEqual(module.plugin_fields, {
            "url": "http://www.example.com/",
            "rev": "abcdefg"
        })

    def test_parse_module_default_rule(self):
        input = dedent("""\
            git module bar:
                export: bar
            """)
        scope, imports = parse_string(input)
        self.assertIn("bar", scope.modules)
        module = scope.modules["bar"]
        self.assertIsInstance(module, Module)
        self.assertIsInstance(module.default_rule, Rule)
        self.assertEqual(module.default_rule.export, "bar")

    def test_parse_toplevel_imports(self):
        input = dedent("""\
            imports:
                foo: bar/
            """)
        scope, imports = parse_string(input)
        self.assertDictEqual(scope.modules, {})
        self.assertDictEqual(scope.rules, {})
        self.assertEqual(imports, {'foo': ('bar/', )})

    def test_parse_multimap_imports(self):
        input = dedent('''\
            imports:
                foo:
                  - bar/
            ''')
        scope, imports = parse_string(input)
        self.assertDictEqual(scope.modules, {})
        self.assertDictEqual(scope.rules, {})
        self.assertEqual(imports, {'foo': ('bar/', )})

    def test_parse_empty_imports(self):
        input = dedent('''\
            imports:
            ''')
        scope, imports = parse_string(input)
        self.assertDictEqual(scope.modules, {})
        self.assertDictEqual(scope.rules, {})
        self.assertEqual(imports, {})

    def test_parse_wrong_type_imports_throw(self):
        with self.assertRaises(ParserError):
            parse_string('imports: 5')

    def test_bad_toplevel_field_throw(self):
        with self.assertRaises(ParserError):
            parse_string("foo: bar")

    def test_bad_rule_field_throw(self):
        with self.assertRaises(ParserError):
            parse_string(
                dedent("""\
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
                bar: 123
                # These booleans should turn into "true" and "false".
                baz: yes
                bing: no
            ''')
        scope, imports = parse_string(input)
        foo = scope.modules['foo']
        self.assertDictEqual(foo.plugin_fields, {
            "bar": "123",
            "baz": "true",
            "bing": "false",
        })

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

    def test_name_prefix(self):
        input = dedent('''\
            git module foo:
                url: fun stuff

            rule bar:
                export: more stuff
            ''')
        scope, imports = parse_string(input, name_prefix='x')
        # Lookup keys should be unaffected, but the names that modules and
        # rules give for themselves should have the prefix.
        assert scope.modules['foo'].name == 'xfoo'
        assert scope.rules['bar'].name == 'xbar'

    def test_forgotten_colon(self):
        # There are many different permutations of this error, and this only
        # tests the one mentioned in
        # https://github.com/keybase/client/issues/242.
        # TODO: A more general data validation library might help the parser do
        # a better job of checking these things. See
        # https://github.com/buildinspace/peru/issues/40.
        input = dedent('''\
            rule test:
                pick bla
            ''')
        with self.assertRaises(ParserError):
            parse_string(input)

    def test_duplicate_key_heuristic(self):
        yaml = dedent('''\
            a:
                a: 1
                b: 1
            b:
                a: 1
                b: 1
                a: 1
            a : whitespace before colon
            a: stuff
        ''')
        duplicates = parser._get_duplicate_keys_approximate(yaml)
        self.assertEqual([
            ('a', 5, 7),
            ('a', 1, 8),
            ('a', 8, 9),
        ], duplicates)

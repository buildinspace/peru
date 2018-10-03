from textwrap import dedent

import yaml

from peru import edit_yaml
import shared

yaml_template = dedent("""\
    a:
      b: [1, 2, 3]
      c: {}
    d: blarg
    """)


class EditYamlTest(shared.PeruTest):
    def test_replace(self):
        start_yaml = yaml_template.format("foo")
        new_yaml = edit_yaml.set_module_field(start_yaml, "a", "c", "bar")
        self.assertEqual(yaml_template.format("bar"), new_yaml)

    def test_insert(self):
        start_yaml = dedent("""\
            a:
               b: foo
              """)
        new_yaml = edit_yaml.set_module_field(start_yaml, "a", "c", "bar")
        self.assertEqual(start_yaml + "   c: bar\n", new_yaml)

    def test_insert_number_looking_fields(self):
        # These all need to be quoted, or else YAML will interpret them as
        # literal ints and floats.
        start_yaml = dedent('''\
            a:
              b: foo
            ''')
        intermediate = edit_yaml.set_module_field(start_yaml, 'a', 'c', '5')
        new_yaml = edit_yaml.set_module_field(intermediate, 'a', 'd', '.0')
        expected_yaml = start_yaml + '  c: "5"\n  d: ".0"\n'
        self.assertEqual(expected_yaml, new_yaml)
        self.assertDictEqual(
            yaml.safe_load(new_yaml),
            {'a': {
                'b': 'foo',
                'c': '5',
                'd': '.0',
            }})

    def test_insert_with_last_field_as_dict(self):
        start_yaml = dedent("""\
            a:
              b:
                foo: bar
                baz: bing
            x: y
            """)
        end_yaml = dedent("""\
            a:
              b:
                foo: bar
                baz: bing
              c: stuff
            x: y
            """)
        edited_yaml = edit_yaml.set_module_field(start_yaml, "a", "c", "stuff")
        self.assertEqual(end_yaml, edited_yaml)

    def test_with_file(self):
        tmp_name = shared.tmp_file()
        start_yaml = yaml_template.format("foo")
        with open(tmp_name, "w") as f:
            f.write(start_yaml)
        edit_yaml.set_module_field_in_file(tmp_name, "a", "c", "bar")
        with open(tmp_name) as f:
            new_yaml = f.read()
        self.assertEqual(yaml_template.format("bar"), new_yaml)

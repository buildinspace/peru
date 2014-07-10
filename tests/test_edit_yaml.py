from textwrap import dedent
import unittest

from peru import edit_yaml
import shared


yaml_template = dedent("""\
    a:
      b: [1, 2, 3]
      c: {}
    d: blarg
    """)


class EditYamlTest(unittest.TestCase):

    def testReplace(self):
        start_yaml = yaml_template.format("foo")
        new_yaml = edit_yaml.set_module_field(start_yaml, "a", "c", "bar")
        self.assertEqual(yaml_template.format("bar"), new_yaml)

    def testInsert(self):
        start_yaml = dedent("""\
            a:
               b: 5
              """)
        new_yaml = edit_yaml.set_module_field(start_yaml, "a", "c", "9")
        self.assertEqual(start_yaml + "   c: 9\n", new_yaml)

    def testInsertWithLastFieldAsDict(self):
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

    def testWithFile(self):
        tmp_name = shared.tmp_file()
        start_yaml = yaml_template.format("foo")
        with open(tmp_name, "w") as f:
            f.write(start_yaml)
        edit_yaml.set_module_field_in_file(tmp_name, "a", "c", "bar")
        with open(tmp_name) as f:
            new_yaml = f.read()
        self.assertEqual(yaml_template.format("bar"), new_yaml)

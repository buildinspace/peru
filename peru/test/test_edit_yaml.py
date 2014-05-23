from textwrap import dedent
import unittest

from peru import edit_yaml
from peru.test import shared


yaml_template = dedent("""\
    a:
      b: [1, 2, 3]
      c: {}
    d: blarg
    """)


class EditYamlTest(unittest.TestCase):

    def testReplace(self):
        start_yaml = yaml_template.format("foo")
        new_yaml = edit_yaml.replace_module_field(start_yaml, "a", "c", "bar")
        self.assertEqual(yaml_template.format("bar"), new_yaml)

    def testWithFile(self):
        tmp_name = shared.tmp_file()
        start_yaml = yaml_template.format("foo")
        with open(tmp_name, "w") as f:
            f.write(start_yaml)
        edit_yaml.replace_module_field_in_file(tmp_name, "a", "c", "bar")
        with open(tmp_name) as f:
            new_yaml = f.read()
        self.assertEqual(yaml_template.format("bar"), new_yaml)

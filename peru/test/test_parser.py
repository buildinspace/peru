import unittest

from peru.parser import parse_string


class ParserTest(unittest.TestCase):

    def test_parse_empty_file(self):
        scope, local_module = parse_string("")
        self.assertDictEqual(scope, {})
        self.assertDictEqual(local_module.imports, {})

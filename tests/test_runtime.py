import os
import unittest

import peru.runtime as runtime

import shared


class RuntimeTest(unittest.TestCase):
    def test_find_peru_file(self):
        test_dir = shared.create_dir({
            'a/find_me': 'junk',
            'a/b/c/junk': 'junk',
        })
        result = runtime.find_peru_file(
            os.path.join(test_dir, 'a', 'b', 'c'),
            'find_me')
        expected = os.path.join(test_dir, 'a', 'find_me')
        self.assertEqual(expected, result)

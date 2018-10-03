import shared

from peru.keyval import KeyVal


class KeyValTest(shared.PeruTest):
    def test_keyval(self):
        root = shared.create_dir()
        tmp_dir = shared.create_dir()
        keyval = KeyVal(root, tmp_dir)
        key = "mykey"
        # keyval should be empty
        self.assertFalse(key in keyval)
        self.assertSetEqual(set(keyval), set())
        # set a key
        keyval[key] = "myval"
        self.assertEqual(keyval[key], "myval")
        self.assertTrue(key in keyval)
        self.assertSetEqual(set(keyval), {key})
        # overwrite the value
        keyval[key] = "anotherval"
        self.assertEqual(keyval[key], "anotherval")
        # instantiate a second keyval on the same dir, should have same content
        another_keyval = KeyVal(root, tmp_dir)
        self.assertTrue(key in another_keyval)
        self.assertEqual(another_keyval[key], "anotherval")
        self.assertSetEqual(set(another_keyval), {key})
        # test deletions
        del keyval[key]
        self.assertFalse(key in keyval)
        self.assertFalse(key in another_keyval)

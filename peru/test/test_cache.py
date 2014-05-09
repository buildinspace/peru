import os
import tempfile
import unittest

from peru.cache import Cache


def tmp_dir():
    tmp_root = "/tmp/perutest"
    os.makedirs(tmp_root, mode=0o777, exist_ok=True)
    return tempfile.mkdtemp(dir=tmp_root)


def create_dir_with_contents(path_contents_map):
    dir = tmp_dir()
    for path, contents in path_contents_map.items():
        full_path = os.path.join(dir, path)
        full_parent = os.path.dirname(full_path)
        if not os.path.isdir(full_parent):
            os.makedirs(full_parent)
        with open(full_path, "w") as f:
            f.write(contents)
    return dir


def read_contents_from_dir(dir):
    contents = {}
    for subdir, _, files in os.walk(dir):
        for file in files:
            path = os.path.normpath(os.path.join(subdir, file))
            with open(path) as f:
                content = f.read()
            relpath = os.path.relpath(path, dir)
            contents[relpath] = content
    return contents


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = Cache(tmp_dir())
        self.content = {
            "a": "foo",
            "b/c": "bar",
        }
        self.content_dir = create_dir_with_contents(self.content)
        self.content_tree = self.cache.import_tree(self.content_dir)

    def test_export_tree(self):
        export_dir = tmp_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        exported_content = read_contents_from_dir(export_dir)
        self.assertDictEqual(self.content, exported_content)

    def test_tree_status_modified(self):
        with open(os.path.join(self.content_dir, "a"), "a") as f:
            f.write("another line")
        modified, deleted = self.cache.tree_status(self.content_tree,
                                                   self.content_dir)
        self.assertSetEqual(modified, {"a"})
        self.assertSetEqual(deleted, set())

    def test_tree_status_deleted(self):
        os.remove(os.path.join(self.content_dir, "a"))
        modified, deleted = self.cache.tree_status(self.content_tree,
                                                   self.content_dir)
        self.assertSetEqual(modified, set())
        self.assertSetEqual(deleted, {"a"})

    def test_merge_trees(self):
        merged_tree = self.cache.merge_trees(self.content_tree,
                                             self.content_tree,
                                             "subdir")
        expected_content = dict(self.content)
        for path, content in self.content.items():
            expected_content[os.path.join("subdir", path)] = content
        export_dir = tmp_dir()
        self.cache.export_tree(merged_tree, export_dir)
        exported_content = read_contents_from_dir(export_dir)
        self.assertDictEqual(exported_content, expected_content)

        with self.assertRaises(Cache.GitError):
            # subdir/ is already populated, so this merge should throw.
            self.cache.merge_trees(merged_tree, self.content_tree, "subdir")

    def test_keyval(self):
        key = "mykey"
        self.assertFalse(key in self.cache.keyval)
        self.cache.keyval[key] = "myval"
        self.assertEqual(self.cache.keyval[key], "myval")
        self.assertTrue(key in self.cache.keyval)
        self.cache.keyval[key] = "anotherval"
        self.assertEqual(self.cache.keyval[key], "anotherval")
        another_cache = Cache(self.cache.root)
        self.assertTrue(key in self.cache.keyval)
        self.assertEqual(another_cache.keyval[key], "anotherval")

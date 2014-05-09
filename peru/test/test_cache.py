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

    def test_basic_export(self):
        export_dir = tmp_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        self.assertDictEqual(self.content, read_contents_from_dir(export_dir))

    def test_multiple_imports(self):
        new_content = {"fee/fi": "fo fum"}
        new_tree = self.cache.import_tree(
            create_dir_with_contents(new_content))
        export_dir = tmp_dir()
        self.cache.export_tree(new_tree, export_dir)
        self.assertDictEqual(new_content, read_contents_from_dir(export_dir))

    def test_export_with_existing_files(self):
        # Create a dir with an existing file that doesn't conflict.
        more_content = {"untracked": "stuff"}
        export_dir = create_dir_with_contents(more_content)
        self.cache.export_tree(self.content_tree, export_dir)
        expected_content = self.content.copy()
        expected_content.update(more_content)
        self.assertDictEqual(expected_content,
                             read_contents_from_dir(export_dir))

        # But if we try to export twice, the export_dir will now have
        # conflicting files, and export_tree() should throw.
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)

    def test_previous_tree(self):
        # Create some new content.
        export_dir = create_dir_with_contents(self.content)
        new_content = {"a": "different", "b/c": "bar"}
        new_dir = create_dir_with_contents(new_content)
        new_tree = self.cache.import_tree(new_dir)

        # Now use cache.export_tree to move from the original content to the
        # different content.
        self.cache.export_tree(new_tree, export_dir,
                               previous_tree=self.content_tree)
        self.assertDictEqual(new_content, read_contents_from_dir(export_dir))

        # Now do the same thing again, but use a dirty working copy. This
        # should cause an error.
        dirty_content = self.content.copy()
        dirty_content["a"] = "dirty"
        dirty_dir = create_dir_with_contents(dirty_content)
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, dirty_dir,
                                   previous_tree=self.content_tree)

        # Make sure we get an error even if the dirty file is unchanged between
        # the previous tree and the new one.
        no_conflict_dirty_content = self.content.copy()
        no_conflict_dirty_content["b/c"] = "dirty"
        no_conflict_dirty_dir = create_dir_with_contents(
            no_conflict_dirty_content)
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, no_conflict_dirty_dir,
                                   previous_tree=self.content_tree)

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

import os
import unittest

from peru.cache import Cache
import shared


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = Cache(shared.create_dir())
        self.content = {
            "a": "foo",
            "b/c": "bar",
            "b/d": "baz",
        }
        self.content_dir = shared.create_dir(self.content)
        self.content_tree = self.cache.import_tree(self.content_dir)

    def test_basic_export(self):
        export_dir = shared.create_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        self.assertDictEqual(self.content, shared.read_dir(export_dir))

    def test_export_force(self):
        # Create a working tree with a conflicting file.
        dirty_content = {"a": "junk"}
        export_dir = shared.create_dir(dirty_content)
        # Export should fail by default.
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)
        self.assertDictEqual(dirty_content, shared.read_dir(export_dir))
        # But it should suceed with the force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True)
        self.assertDictEqual(self.content, shared.read_dir(export_dir))

    def test_multiple_imports(self):
        new_content = {"fee/fi": "fo fum"}
        new_tree = self.cache.import_tree(shared.create_dir(new_content))
        export_dir = shared.create_dir()
        self.cache.export_tree(new_tree, export_dir)
        self.assertDictEqual(new_content, shared.read_dir(export_dir))

    def test_export_with_existing_files(self):
        # Create a dir with an existing file that doesn't conflict.
        more_content = {"untracked": "stuff"}
        export_dir = shared.create_dir(more_content)
        self.cache.export_tree(self.content_tree, export_dir)
        expected_content = self.content.copy()
        expected_content.update(more_content)
        self.assertDictEqual(expected_content, shared.read_dir(export_dir))

        # But if we try to export twice, the export_dir will now have
        # conflicting files, and export_tree() should throw.
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)

    def test_previous_tree(self):
        export_dir = shared.create_dir(self.content)

        # Create some new content.
        new_content = self.content.copy()
        new_content["a"] += " different"
        new_content["newfile"] = "newfile stuff"
        new_dir = shared.create_dir(new_content)
        new_tree = self.cache.import_tree(new_dir)

        # Now use cache.export_tree to move from the original content to the
        # different content.
        self.cache.export_tree(new_tree, export_dir,
                               previous_tree=self.content_tree)
        self.assertDictEqual(new_content, shared.read_dir(export_dir))

        # Now do the same thing again, but use a dirty working copy. This
        # should cause an error.
        dirty_content = self.content.copy()
        dirty_content["a"] += " dirty"
        dirty_dir = shared.create_dir(dirty_content)
        with self.assertRaises(Cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, dirty_dir,
                                   previous_tree=self.content_tree)

        # Make sure we get an error even if the dirty file is unchanged between
        # the previous tree and the new one.
        no_conflict_dirty_content = self.content.copy()
        no_conflict_dirty_content["b/c"] += " dirty"
        no_conflict_dirty_dir = shared.create_dir(no_conflict_dirty_content)
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
        export_dir = shared.create_dir()
        self.cache.export_tree(merged_tree, export_dir)
        exported_content = shared.read_dir(export_dir)
        self.assertDictEqual(exported_content, expected_content)

        with self.assertRaises(Cache.MergeConflictError):
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

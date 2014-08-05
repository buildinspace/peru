import os
import unittest

import peru.cache
import shared


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = peru.cache.Cache(shared.create_dir())
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

    def test_export_force_with_preexisting_files(self):
        # Create a working tree with a conflicting file.
        dirty_content = {"a": "junk"}
        export_dir = shared.create_dir(dirty_content)
        # Export should fail by default.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)
        self.assertDictEqual(dirty_content, shared.read_dir(export_dir))
        # But it should suceed with the force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True)
        self.assertDictEqual(self.content, shared.read_dir(export_dir))

    def test_export_force_with_changed_files(self):
        export_dir = shared.create_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        # If we dirty a file, a resync should fail.
        with open(os.path.join(export_dir, "a"), "w") as f:
            f.write("dirty")
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir,
                                   previous_tree=self.content_tree)
        # But it should succeed with the --force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True,
                               previous_tree=self.content_tree)

    def test_multiple_imports(self):
        new_content = {"fee/fi": "fo fum"}
        new_tree = self.cache.import_tree(shared.create_dir(new_content))
        export_dir = shared.create_dir()
        self.cache.export_tree(new_tree, export_dir)
        self.assertDictEqual(new_content, shared.read_dir(export_dir))

    def test_import_with_gitignore(self):
        # Make sure our git imports don't get confused by .gitignore files.
        new_content = {"fee/fi": "fo fum", ".gitignore": "fee/"}
        new_tree = self.cache.import_tree(shared.create_dir(new_content))
        export_dir = shared.create_dir()
        self.cache.export_tree(new_tree, export_dir)
        self.assertDictEqual(new_content, shared.read_dir(export_dir))

    def test_import_with_files(self):
        all_content = {'foo': '',
                       'bar': '',
                       'baz/bing': ''}
        test_dir = shared.create_dir(all_content)
        tree = self.cache.import_tree(test_dir, ['foo', 'baz'])
        expected_content = {'foo': '',
                            'baz/bing': ''}
        out_dir = shared.create_dir()
        self.cache.export_tree(tree, out_dir)
        actual_content = shared.read_dir(out_dir)
        self.assertDictEqual(expected_content, actual_content)

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
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)

        # By default, git's checkout safety doesn't protect files that are
        # .gitignore'd. Make sure we still throw the right errors in the
        # presence of a .gitignore file.
        with open(os.path.join(export_dir, '.gitignore'), "w") as f:
            f.write('*\n')  # .gitignore everything
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
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
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, dirty_dir,
                                   previous_tree=self.content_tree)
        # But if the file is simply missing, it should work.
        os.remove(os.path.join(dirty_dir, 'a'))
        self.cache.export_tree(new_tree, dirty_dir,
                               previous_tree=self.content_tree)
        self.assertDictEqual(new_content, shared.read_dir(dirty_dir))

        # Make sure we get an error even if the dirty file is unchanged between
        # the previous tree and the new one.
        no_conflict_dirty_content = self.content.copy()
        no_conflict_dirty_content["b/c"] += " dirty"
        no_conflict_dirty_dir = shared.create_dir(no_conflict_dirty_content)
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, no_conflict_dirty_dir,
                                   previous_tree=self.content_tree)

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

        with self.assertRaises(peru.cache.MergeConflictError):
            # subdir/ is already populated, so this merge should throw.
            self.cache.merge_trees(merged_tree, self.content_tree, "subdir")

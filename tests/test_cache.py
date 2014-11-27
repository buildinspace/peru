import os
import unittest

import peru.cache
import shared
from shared import assert_contents


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
        assert_contents(export_dir, self.content)

    def test_export_force_with_preexisting_files(self):
        # Create a working tree with a conflicting file.
        dirty_content = {"a": "junk"}
        export_dir = shared.create_dir(dirty_content)
        # Export should fail by default.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)
        assert_contents(export_dir, dirty_content)
        # But it should suceed with the force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True)
        assert_contents(export_dir, self.content)

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
        assert_contents(export_dir, self.content)

    def test_multiple_imports(self):
        new_content = {"fee/fi": "fo fum"}
        new_tree = self.cache.import_tree(shared.create_dir(new_content))
        export_dir = shared.create_dir()
        self.cache.export_tree(new_tree, export_dir)
        assert_contents(export_dir, new_content)

    def test_import_with_gitignore(self):
        # Make sure our git imports don't get confused by .gitignore files.
        new_content = {"fee/fi": "fo fum", ".gitignore": "fee/"}
        new_tree = self.cache.import_tree(shared.create_dir(new_content))
        export_dir = shared.create_dir()
        self.cache.export_tree(new_tree, export_dir)
        assert_contents(export_dir, new_content)

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
        assert_contents(out_dir, expected_content)

    def test_export_with_existing_files(self):
        # Create a dir with an existing file that doesn't conflict.
        more_content = {"untracked": "stuff"}
        export_dir = shared.create_dir(more_content)
        self.cache.export_tree(self.content_tree, export_dir)
        expected_content = self.content.copy()
        expected_content.update(more_content)
        assert_contents(export_dir, expected_content)

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
        assert_contents(export_dir, new_content)

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
        assert_contents(dirty_dir, new_content)

        # Make sure we get an error even if the dirty file is unchanged between
        # the previous tree and the new one.
        no_conflict_dirty_content = self.content.copy()
        no_conflict_dirty_content["b/c"] += " dirty"
        no_conflict_dirty_dir = shared.create_dir(no_conflict_dirty_content)
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, no_conflict_dirty_dir,
                                   previous_tree=self.content_tree)

    def test_missing_files_in_previous_tree(self):
        '''Export should allow missing files, and it should recreate them.'''
        export_dir = shared.create_dir()
        # Nothing in content_tree exists yet, so this export should be the same
        # as if previous_tree wasn't specified.
        self.cache.export_tree(self.content_tree, export_dir,
                               previous_tree=self.content_tree)
        assert_contents(export_dir, self.content)
        # Make sure the same applies with just a single missing file.
        os.remove(os.path.join(export_dir, 'a'))
        self.cache.export_tree(self.content_tree, export_dir,
                               previous_tree=self.content_tree)
        assert_contents(export_dir, self.content)

    def test_merge_trees(self):
        merged_tree = self.cache.merge_trees(self.content_tree,
                                             self.content_tree,
                                             "subdir")
        expected_content = dict(self.content)
        for path, content in self.content.items():
            expected_content[os.path.join("subdir", path)] = content
        export_dir = shared.create_dir()
        self.cache.export_tree(merged_tree, export_dir)
        assert_contents(export_dir, expected_content)

        with self.assertRaises(peru.cache.MergeConflictError):
            # subdir/ is already populated, so this merge should throw.
            self.cache.merge_trees(merged_tree, self.content_tree, "subdir")

    def test_merge_with_deep_prefix(self):
        '''This test was inspired by a bug on Windows where we would give git a
        backslash-separated merge prefix, even though git demands forward slash
        as a path separator.'''
        content = {'file': 'stuff'}
        content_dir = shared.create_dir(content)
        tree = self.cache.import_tree(content_dir)
        prefixed_tree = self.cache.merge_trees(None, tree, 'a/b/')
        export_dir = shared.create_dir()
        self.cache.export_tree(prefixed_tree, export_dir)
        assert_contents(export_dir, {'a/b/file': 'stuff'})

    def test_read_file(self):
        self.assertEqual(
            b'foo', self.cache.read_file(self.content_tree, 'a'))
        self.assertEqual(
            b'bar', self.cache.read_file(self.content_tree, 'b/c'))

    # A helper method for several tests below below.
    def do_excludes_and_files_test(self, excludes, files, expected):
        tree = self.cache.import_tree(self.content_dir, excludes=excludes,
                                      files=files)
        out_dir = shared.create_dir()
        self.cache.export_tree(tree, out_dir)
        assert_contents(out_dir, expected)

    def test_import_with_specific_file(self):
        self.do_excludes_and_files_test(
            excludes=[], files=['a'], expected={'a': 'foo'})

    def test_import_with_specific_dir(self):
        self.do_excludes_and_files_test(
            excludes=[], files=['b'], expected={'b/c': 'bar', 'b/d': 'baz'})

    def test_import_with_excluded_file(self):
        self.do_excludes_and_files_test(
            excludes=['a'], files=[], expected={'b/c': 'bar', 'b/d': 'baz'})

    def test_import_with_excluded_dir(self):
        self.do_excludes_and_files_test(
            excludes=['b'], files=[], expected={'a': 'foo'})

    def test_import_with_excludes_and_files(self):
        self.do_excludes_and_files_test(
            excludes=['b/c'], files=['b'], expected={'b/d': 'baz'})

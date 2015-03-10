import os
import unittest

import peru.cache
from shared import assert_contents, create_dir


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = peru.cache.Cache(create_dir())
        self.content = {
            'a': 'foo',
            'b/c': 'bar',
            'b/d': 'baz',
        }
        self.content_dir = create_dir(self.content)
        self.content_tree = self.cache.import_tree(self.content_dir)

    def test_basic_export(self):
        export_dir = create_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        assert_contents(export_dir, self.content)

    def test_export_force_with_preexisting_files(self):
        # Create a working tree with a conflicting file.
        dirty_content = {'a': 'junk'}
        export_dir = create_dir(dirty_content)
        # Export should fail by default.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)
        assert_contents(export_dir, dirty_content)
        # But it should suceed with the force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True)
        assert_contents(export_dir, self.content)

    def test_export_force_with_changed_files(self):
        export_dir = create_dir()
        self.cache.export_tree(self.content_tree, export_dir)
        # If we dirty a file, a resync should fail.
        with open(os.path.join(export_dir, 'a'), 'w') as f:
            f.write('dirty')
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir,
                                   previous_tree=self.content_tree)
        # But it should succeed with the --force flag.
        self.cache.export_tree(self.content_tree, export_dir, force=True,
                               previous_tree=self.content_tree)
        assert_contents(export_dir, self.content)

    def test_multiple_imports(self):
        new_content = {'fee/fi': 'fo fum'}
        new_tree = self.cache.import_tree(create_dir(new_content))
        export_dir = create_dir()
        self.cache.export_tree(new_tree, export_dir)
        assert_contents(export_dir, new_content)

    def test_import_with_gitignore(self):
        # Make sure our git imports don't get confused by .gitignore files.
        new_content = {'fee/fi': 'fo fum', '.gitignore': 'fee/'}
        new_tree = self.cache.import_tree(create_dir(new_content))
        export_dir = create_dir()
        self.cache.export_tree(new_tree, export_dir)
        assert_contents(export_dir, new_content)

    def test_import_with_files(self):
        all_content = {'foo': '',
                       'bar': '',
                       'baz/bing': ''}
        test_dir = create_dir(all_content)
        tree = self.cache.import_tree(test_dir, picks=['foo', 'baz'])
        expected_content = {'foo': '',
                            'baz/bing': ''}
        out_dir = create_dir()
        self.cache.export_tree(tree, out_dir)
        assert_contents(out_dir, expected_content)

    def test_export_with_existing_files(self):
        # Create a dir with an existing file that doesn't conflict.
        more_content = {'untracked': 'stuff'}
        export_dir = create_dir(more_content)
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
        with open(os.path.join(export_dir, '.gitignore'), 'w') as f:
            f.write('*\n')  # .gitignore everything
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(self.content_tree, export_dir)

    def test_previous_tree(self):
        export_dir = create_dir(self.content)

        # Create some new content.
        new_content = self.content.copy()
        new_content['a'] += ' different'
        new_content['newfile'] = 'newfile stuff'
        new_dir = create_dir(new_content)
        new_tree = self.cache.import_tree(new_dir)

        # Now use cache.export_tree to move from the original content to the
        # different content.
        self.cache.export_tree(new_tree, export_dir,
                               previous_tree=self.content_tree)
        assert_contents(export_dir, new_content)

        # Now do the same thing again, but use a dirty working copy. This
        # should cause an error.
        dirty_content = self.content.copy()
        dirty_content['a'] += ' dirty'
        dirty_dir = create_dir(dirty_content)
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
        no_conflict_dirty_content['b/c'] += ' dirty'
        no_conflict_dirty_dir = create_dir(no_conflict_dirty_content)
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.cache.export_tree(new_tree, no_conflict_dirty_dir,
                                   previous_tree=self.content_tree)

    def test_missing_files_in_previous_tree(self):
        '''Export should allow missing files, and it should recreate them.'''
        export_dir = create_dir()
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
                                             'subdir')
        expected_content = dict(self.content)
        for path, content in self.content.items():
            expected_content[os.path.join('subdir', path)] = content
        export_dir = create_dir()
        self.cache.export_tree(merged_tree, export_dir)
        assert_contents(export_dir, expected_content)

        with self.assertRaises(peru.cache.MergeConflictError):
            # subdir/ is already populated, so this merge should throw.
            self.cache.merge_trees(merged_tree, self.content_tree, 'subdir')

    def test_merge_with_deep_prefix(self):
        '''This test was inspired by a bug on Windows where we would give git a
        backslash-separated merge prefix, even though git demands forward slash
        as a path separator.'''
        content = {'file': 'stuff'}
        content_dir = create_dir(content)
        tree = self.cache.import_tree(content_dir)
        prefixed_tree = self.cache.merge_trees(None, tree, 'a/b/')
        export_dir = create_dir()
        self.cache.export_tree(prefixed_tree, export_dir)
        assert_contents(export_dir, {'a/b/file': 'stuff'})

    def test_read_file(self):
        self.assertEqual(
            b'foo', self.cache.read_file(self.content_tree, 'a'))
        self.assertEqual(
            b'bar', self.cache.read_file(self.content_tree, 'b/c'))
        with self.assertRaises(FileNotFoundError):
            self.cache.read_file(self.content_tree, 'nonexistent')
        with self.assertRaises(IsADirectoryError):
            self.cache.read_file(self.content_tree, 'b')

    # A helper method for several tests below below.
    def do_excludes_and_files_test(self, excludes, picks, expected):
        tree = self.cache.import_tree(self.content_dir, excludes=excludes,
                                      picks=picks)
        out_dir = create_dir()
        self.cache.export_tree(tree, out_dir)
        assert_contents(out_dir, expected)

    def test_import_with_specific_file(self):
        self.do_excludes_and_files_test(
            excludes=[], picks=['a'], expected={'a': 'foo'})

    def test_import_with_specific_dir(self):
        self.do_excludes_and_files_test(
            excludes=[], picks=['b'], expected={'b/c': 'bar', 'b/d': 'baz'})

    def test_import_with_excluded_file(self):
        self.do_excludes_and_files_test(
            excludes=['a'], picks=[], expected={'b/c': 'bar', 'b/d': 'baz'})

    def test_import_with_excluded_dir(self):
        self.do_excludes_and_files_test(
            excludes=['b'], picks=[], expected={'a': 'foo'})

    def test_import_with_excludes_and_files(self):
        self.do_excludes_and_files_test(
            excludes=['b/c'], picks=['b'], expected={'b/d': 'baz'})

    def test_ls_tree(self):
        # Use the recursive case to get valid entries for each file. We could
        # hardcode these, but it would be messy and annoying to maintain.
        entries = self.cache.ls_tree(self.content_tree, recursive=True)
        assert entries.keys() == {'a', 'b', 'b/c', 'b/d'}
        assert (entries['a'].type == entries['b/c'].type ==
                entries['b/d'].type == peru.cache.BLOB_TYPE)
        assert entries['b'].type == peru.cache.TREE_TYPE

        # Check the non-recursive, non-path case.
        self.assertDictEqual({'a': entries['a'], 'b': entries['b']},
                             self.cache.ls_tree(self.content_tree))

        # Check the single file case, and make sure paths are normalized.
        self.assertDictEqual({'b/c': entries['b/c']},
                             self.cache.ls_tree(self.content_tree, 'b/c//./'))

        # Check the single dir case. (Trailing slash shouldn't matter, because
        # we nomalize it, but git will do the wrong thing if we forget
        # normalization.)
        self.assertDictEqual({'b': entries['b']},
                             self.cache.ls_tree(self.content_tree, 'b/'))

        # Check the recursive dir case.
        self.assertDictEqual(
            {'b': entries['b'], 'b/c': entries['b/c'], 'b/d': entries['b/d']},
            self.cache.ls_tree(self.content_tree, 'b', recursive=True))

        # Make sure that we don't skip over a target file in recursive mode.
        self.assertDictEqual({'b/c': entries['b/c']},
                             self.cache.ls_tree(self.content_tree, 'b/c',
                                                recursive=True))

    def test_modify_tree(self):
        base_dir = create_dir({'a': 'foo', 'b/c': 'bar'})
        base_tree = self.cache.import_tree(base_dir)
        entries = self.cache.ls_tree(base_tree, recursive=True)
        cases = []

        # Test regular deletions.
        cases.append(({'a': None},
                      {'b/c': 'bar'}))
        cases.append(({'a//./': None},  # Paths should get normalized.
                      {'b/c': 'bar'}))
        cases.append(({'b': None},
                      {'a': 'foo'}))
        cases.append(({'b/c': None},
                      {'a': 'foo'}))
        cases.append(({'x/y/z': None},
                      {'a': 'foo', 'b/c': 'bar'}))
        cases.append(({'b/x': None},
                      {'a': 'foo', 'b/c': 'bar'}))
        # Test the case where we try to delete below a file.
        cases.append(({'a/x': None},
                      {'a': 'foo', 'b/c': 'bar'}))
        # Test insertions.
        cases.append(({'b': entries['a']},
                      {'a': 'foo', 'b': 'foo'}))
        cases.append(({'x': entries['a']},
                      {'a': 'foo', 'x': 'foo', 'b/c': 'bar'}))
        cases.append(({'x': entries['b']},
                      {'a': 'foo', 'b/c': 'bar', 'x/c': 'bar'}))
        cases.append(({'d/e/f': entries['a']},
                      {'a': 'foo', 'b/c': 'bar', 'd/e/f': 'foo'}))
        cases.append(({'d/e/f': entries['b']},
                      {'a': 'foo', 'b/c': 'bar', 'd/e/f/c': 'bar'}))

        for modifications, result in cases:
            modified_tree = self.cache.modify_tree(base_tree, modifications)
            modified_dir = create_dir()
            self.cache.export_tree(modified_tree, modified_dir)
            error_msg = ('modify_tree failed to give result {} '
                         'for modifications {}'.format(
                             repr(result), repr(modifications)))
            assert_contents(modified_dir, result, message=error_msg)

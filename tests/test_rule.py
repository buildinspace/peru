import os
import unittest

from peru import cache
from peru import rule

import shared


class RuleTest(unittest.TestCase):

    def setUp(self):
        self.cache_dir = shared.create_dir()
        self.cache = cache.Cache(self.cache_dir)
        self.content = {'a': 'foo', 'b/c': 'bar'}
        self.content_dir = shared.create_dir(self.content)
        self.content_tree = self.cache.import_tree(self.content_dir)
        self.entries = self.cache.ls_tree(self.content_tree, recursive=True)

    def test_copy(self):
        # A file copied into a directory should be placed into that directory.
        # A directory or file copied into a file should overwrite that file.
        copies = {'a': ['x', 'b', 'b/c'], 'b': ['a', 'y']}
        tree = rule.copy_files(self.cache, self.content_tree, copies)
        shared.assert_tree_contents(self.cache, tree, {
            'a/c': 'bar',
            'b/a': 'foo',
            'b/c': 'foo',
            'x':   'foo',
            'y/c': 'bar',
        })

    def test_move(self):
        # Same semantics as copy above. Also, make sure that move deletes move
        # sources, but does not delete sources that were overwritten by the
        # target of another move.
        moves = {'a': 'b', 'b': 'a'}
        tree = rule.move_files(self.cache, self.content_tree, moves)
        shared.assert_tree_contents(self.cache, tree, {
            'a/c': 'bar',
            'b/a': 'foo',
        })

    def test_pick(self):
        pick_dir = rule.pick_files(self.cache, self.content_tree, ['b'])
        shared.assert_tree_contents(self.cache, pick_dir, {'b/c': 'bar'})

        pick_file = rule.pick_files(self.cache, self.content_tree, ['a'])
        shared.assert_tree_contents(self.cache, pick_file, {'a': 'foo'})

        globs = rule.pick_files(self.cache, self.content_tree,
                                ['**/c', '**/a'])
        shared.assert_tree_contents(self.cache, globs,
                                    {'a': 'foo', 'b/c': 'bar'})

    def test_executable(self):
        exe = rule.make_files_executable(self.cache, self.content_tree,
                                         ['b/*'])
        new_content_dir = shared.create_dir()
        self.cache.export_tree(exe, new_content_dir)
        shared.assert_contents(new_content_dir, self.content)
        shared.assert_not_executable(os.path.join(new_content_dir, 'a'))
        shared.assert_executable(os.path.join(new_content_dir, 'b/c'))

    def test_export(self):
        b = rule.get_export_tree(self.cache, self.content_tree, 'b')
        shared.assert_tree_contents(self.cache, b, {'c': 'bar'})

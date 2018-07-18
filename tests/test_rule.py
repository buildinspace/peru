import os

from peru import cache
from peru import rule

import shared


class RuleTest(shared.PeruTest):

    @shared.make_synchronous
    def setUp(self):
        self.cache_dir = shared.create_dir()
        self.cache = yield from cache.Cache(self.cache_dir)
        # Include a leading colon to test that we prepend ./ to pathspecs.
        self.content = {'a': 'foo', 'b/c': 'bar', ':d': 'baz'}
        self.content_dir = shared.create_dir(self.content)
        self.content_tree = yield from self.cache.import_tree(self.content_dir)
        self.entries = yield from self.cache.ls_tree(
            self.content_tree, recursive=True)

    @shared.make_synchronous
    def test_copy(self):
        # A file copied into a directory should be placed into that directory.
        # A directory or file copied into a file should overwrite that file.
        copies = {'a': ['x', 'b', 'b/c'], 'b': ['a', 'y']}
        tree = yield from rule.copy_files(
            self.cache, self.content_tree, copies)
        yield from shared.assert_tree_contents(self.cache, tree, {
            'a/c': 'bar',
            'b/a': 'foo',
            'b/c': 'foo',
            'x':   'foo',
            'y/c': 'bar',
            ':d':  'baz',
        })

    @shared.make_synchronous
    def test_move(self):
        # Same semantics as copy above. Also, make sure that move deletes move
        # sources, but does not delete sources that were overwritten by the
        # target of another move.
        moves = {'a': 'b', 'b': 'a'}
        tree = yield from rule.move_files(self.cache, self.content_tree, moves)
        yield from shared.assert_tree_contents(self.cache, tree, {
            'a/c': 'bar',
            'b/a': 'foo',
            ':d':  'baz',
        })

    @shared.make_synchronous
    def test_drop(self):
        drop_dir = yield from rule.drop_files(
            self.cache, self.content_tree, ['b'])
        yield from shared.assert_tree_contents(
            self.cache, drop_dir, {'a': 'foo', ':d': 'baz'})

        drop_file = yield from rule.drop_files(
            self.cache, self.content_tree, ['a'])
        yield from shared.assert_tree_contents(
            self.cache, drop_file, {'b/c': 'bar', ':d': 'baz'})

        drop_colon = yield from rule.drop_files(
            self.cache, self.content_tree, [':d'])
        yield from shared.assert_tree_contents(
            self.cache, drop_colon, {'a': 'foo', 'b/c': 'bar'})

        globs = yield from rule.drop_files(
            self.cache, self.content_tree, ['**/c', '**/a'])
        yield from shared.assert_tree_contents(
            self.cache, globs, {':d': 'baz'})

    @shared.make_synchronous
    def test_pick(self):
        pick_dir = yield from rule.pick_files(
            self.cache, self.content_tree, ['b'])
        yield from shared.assert_tree_contents(
            self.cache, pick_dir, {'b/c': 'bar'})

        pick_file = yield from rule.pick_files(
            self.cache, self.content_tree, ['a'])
        yield from shared.assert_tree_contents(
            self.cache, pick_file, {'a': 'foo'})

        pick_colon = yield from rule.pick_files(
            self.cache, self.content_tree, [':d'])
        yield from shared.assert_tree_contents(
            self.cache, pick_colon, {':d': 'baz'})

        globs = yield from rule.pick_files(
            self.cache, self.content_tree, ['**/c', '**/a'])
        yield from shared.assert_tree_contents(
            self.cache, globs, {'a': 'foo', 'b/c': 'bar'})

    @shared.make_synchronous
    def test_executable(self):
        exe = yield from rule.make_files_executable(
            self.cache, self.content_tree, ['b/*'])
        new_content_dir = shared.create_dir()
        yield from self.cache.export_tree(exe, new_content_dir)
        shared.assert_contents(new_content_dir, self.content)
        shared.assert_not_executable(os.path.join(new_content_dir, 'a'))
        shared.assert_executable(os.path.join(new_content_dir, 'b/c'))

    @shared.make_synchronous
    def test_export(self):
        b = yield from rule.get_export_tree(
            self.cache, self.content_tree, 'b')
        yield from shared.assert_tree_contents(self.cache, b, {'c': 'bar'})

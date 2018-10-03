import os

from peru import cache
from peru import rule

import shared
from shared import COLON


class RuleTest(shared.PeruTest):
    @shared.make_synchronous
    async def setUp(self):
        self.cache_dir = shared.create_dir()
        self.cache = await cache.Cache(self.cache_dir)
        # Include a leading colon to test that we prepend ./ to pathspecs.
        self.content = {'a': 'foo', 'b/c': 'bar', COLON + 'd': 'baz'}
        self.content_dir = shared.create_dir(self.content)
        self.content_tree = await self.cache.import_tree(self.content_dir)
        self.entries = await self.cache.ls_tree(
            self.content_tree, recursive=True)

    @shared.make_synchronous
    async def test_copy(self):
        # A file copied into a directory should be placed into that directory.
        # A directory or file copied into a file should overwrite that file.
        copies = {'a': ['x', 'b', 'b/c'], 'b': ['a', 'y']}
        tree = await rule.copy_files(self.cache, self.content_tree, copies)
        await shared.assert_tree_contents(
            self.cache, tree, {
                'a/c': 'bar',
                'b/a': 'foo',
                'b/c': 'foo',
                'x': 'foo',
                'y/c': 'bar',
                COLON + 'd': 'baz',
            })

    @shared.make_synchronous
    async def test_move(self):
        # Same semantics as copy above. Also, make sure that move deletes move
        # sources, but does not delete sources that were overwritten by the
        # target of another move.
        moves = {'a': 'b', 'b': 'a'}
        tree = await rule.move_files(self.cache, self.content_tree, moves)
        await shared.assert_tree_contents(self.cache, tree, {
            'a/c': 'bar',
            'b/a': 'foo',
            COLON + 'd': 'baz',
        })

    @shared.make_synchronous
    async def test_drop(self):
        drop_dir = await rule.drop_files(self.cache, self.content_tree, ['b'])
        await shared.assert_tree_contents(self.cache, drop_dir, {
            'a': 'foo',
            COLON + 'd': 'baz'
        })

        drop_file = await rule.drop_files(self.cache, self.content_tree, ['a'])
        await shared.assert_tree_contents(self.cache, drop_file, {
            'b/c': 'bar',
            COLON + 'd': 'baz'
        })

        drop_colon = await rule.drop_files(self.cache, self.content_tree,
                                           [COLON + 'd'])
        await shared.assert_tree_contents(self.cache, drop_colon, {
            'a': 'foo',
            'b/c': 'bar'
        })

        globs = await rule.drop_files(self.cache, self.content_tree,
                                      ['**/c', '**/a'])
        await shared.assert_tree_contents(self.cache, globs,
                                          {COLON + 'd': 'baz'})

    @shared.make_synchronous
    async def test_pick(self):
        pick_dir = await rule.pick_files(self.cache, self.content_tree, ['b'])
        await shared.assert_tree_contents(self.cache, pick_dir, {'b/c': 'bar'})

        pick_file = await rule.pick_files(self.cache, self.content_tree, ['a'])
        await shared.assert_tree_contents(self.cache, pick_file, {'a': 'foo'})

        pick_colon = await rule.pick_files(self.cache, self.content_tree,
                                           [COLON + 'd'])
        await shared.assert_tree_contents(self.cache, pick_colon,
                                          {COLON + 'd': 'baz'})

        globs = await rule.pick_files(self.cache, self.content_tree,
                                      ['**/c', '**/a'])
        await shared.assert_tree_contents(self.cache, globs, {
            'a': 'foo',
            'b/c': 'bar'
        })

    @shared.make_synchronous
    async def test_executable(self):
        exe = await rule.make_files_executable(self.cache, self.content_tree,
                                               ['b/*'])
        new_content_dir = shared.create_dir()
        await self.cache.export_tree(exe, new_content_dir)
        shared.assert_contents(new_content_dir, self.content)
        shared.assert_not_executable(os.path.join(new_content_dir, 'a'))
        shared.assert_executable(os.path.join(new_content_dir, 'b/c'))

    @shared.make_synchronous
    async def test_export(self):
        b = await rule.get_export_tree(self.cache, self.content_tree, 'b')
        await shared.assert_tree_contents(self.cache, b, {'c': 'bar'})

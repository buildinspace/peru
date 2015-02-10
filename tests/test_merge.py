import unittest

from peru.cache import Cache
from peru.merge import merge_imports_tree

from shared import create_dir, assert_contents


class MergeTest(unittest.TestCase):

    def setUp(self):
        self.cache_dir = create_dir()
        self.cache = Cache(self.cache_dir)

        # These tests use this simple one-file tree as module contents.
        content = {'a': 'a'}
        content_dir = create_dir(content)
        self.content_tree = self.cache.import_tree(content_dir)

    def test_merge_from_map(self):
        imports = {'foo': ('path1',), 'bar': ('path2',)}
        target_trees = {'foo': self.content_tree, 'bar': self.content_tree}

        merged_tree = merge_imports_tree(self.cache, imports, target_trees)

        merged_dir = create_dir()
        self.cache.export_tree(merged_tree, merged_dir)
        expected_content = {'path1/a': 'a', 'path2/a': 'a'}
        assert_contents(merged_dir, expected_content)

    def test_merge_from_multimap(self):
        # This represents a list of key-value pairs in YAML, for example:
        #     imports:
        #         foo:
        #           - path1
        #           - path2
        imports = {'foo': ('path1', 'path2')}
        target_trees = {'foo': self.content_tree}

        merged_tree = merge_imports_tree(self.cache, imports, target_trees)

        merged_dir = create_dir()
        self.cache.export_tree(merged_tree, merged_dir)
        expected_content = {'path1/a': 'a', 'path2/a': 'a'}
        assert_contents(merged_dir, expected_content)

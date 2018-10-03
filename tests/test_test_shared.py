import os
from pathlib import Path

import shared


class SharedTestCodeTest(shared.PeruTest):
    def test_create_dir(self):
        empty_dir = shared.create_dir()
        self.assertListEqual([], os.listdir(empty_dir))
        content = {Path('foo'): 'a', Path('bar/baz'): 'b'}
        content_dir = shared.create_dir(content)
        # Don't use read_dir, because the read_dir test relies on create_dir.
        actual_content = {}
        for p in Path(content_dir).glob('**/*'):
            if p.is_dir():
                continue
            with p.open() as f:
                actual_content[p.relative_to(content_dir)] = f.read()
        self.assertDictEqual(content, actual_content)

    def test_read_dir(self):
        content = {Path('foo'): 'a', Path('bar/baz'): 'b'}
        test_dir = shared.create_dir(content)
        read_content = shared.read_dir(test_dir)
        self.assertDictEqual(content, read_content)
        self.assertDictEqual({
            Path('foo'): 'a'
        }, shared.read_dir(test_dir, excludes=['bar']))
        self.assertDictEqual({
            Path('foo'): 'a'
        }, shared.read_dir(test_dir, excludes=['bar/baz']))

    def test_assert_contents(self):
        content = {'foo': 'a', 'bar/baz': 'b'}
        test_dir = shared.create_dir(content)
        shared.assert_contents(test_dir, content)
        shared.write_files(test_dir, {'bing': 'c'})
        with self.assertRaises(AssertionError):
            shared.assert_contents(test_dir, content)
        shared.assert_contents(test_dir, content, excludes=['bing'])
        try:
            shared.assert_contents(test_dir, content, excludes=['foo'])
        except AssertionError as e:
            assert e.args[0].startswith('EXPECTED FILES WERE EXCLUDED')

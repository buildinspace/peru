import os
from textwrap import dedent
import unittest

import shared
from shared import run_peru_command, assert_contents


class ReupIntegrationTest(unittest.TestCase):
    def setUp(self):
        template = dedent('''\
            git module foo:
                url: {}
                rev: master

            git module bar:
                url: {}
                reup: otherbranch
            ''')
        self.foo_dir = shared.create_dir({'a': 'b'})
        self.foo_repo = shared.GitRepo(self.foo_dir)
        self.foo_master = self.foo_repo.run('git', 'rev-parse', 'master')
        self.bar_dir = shared.create_dir()
        self.bar_repo = shared.GitRepo(self.bar_dir)
        self.bar_repo.run('git', 'checkout', '-q', '-b', 'otherbranch')
        self.bar_repo.run('git', 'commit', '--allow-empty', '-m', 'junk')
        self.bar_otherbranch = self.bar_repo.run(
            'git', 'rev-parse', 'otherbranch')
        self.start_yaml = template.format(self.foo_dir, self.bar_dir)
        self.test_dir = shared.create_dir({'peru.yaml': self.start_yaml})

    def tearDown(self):
        shared.assert_clean_tmp(os.path.join(self.test_dir, '.peru'))

    def test_single_reup(self):
        expected = dedent('''\
            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
            ''').format(self.foo_dir, self.foo_master, self.bar_dir)
        run_peru_command(['reup', 'foo'], self.test_dir)
        assert_contents(self.test_dir, {'peru.yaml': expected},
                        excludes=['.peru'])

    def test_reup_sync(self):
        yaml_with_imports = dedent('''\
            imports:
                foo: ./
                bar: ./

            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
            ''').format(self.foo_dir, self.foo_master, self.bar_dir)
        test_dir = shared.create_dir({'peru.yaml': yaml_with_imports})
        # First reup without the sync.
        run_peru_command(['reup', 'foo', '--nosync'], test_dir)
        assert_contents(test_dir, {}, excludes=['.peru', 'peru.yaml'])
        # Now do it with the sync.
        run_peru_command(['reup', 'foo', '--quiet'], test_dir)
        assert_contents(test_dir, {'a': 'b'}, excludes=['.peru', 'peru.yaml'])

    def test_reup_all(self):
        expected = dedent('''\
            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
                rev: {}
            ''').format(self.foo_dir, self.foo_master, self.bar_dir,
                        self.bar_otherbranch)
        run_peru_command(['reup'], self.test_dir)
        assert_contents(self.test_dir, {'peru.yaml': expected},
                        excludes=['.peru'])

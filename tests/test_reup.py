import os
from textwrap import dedent

import shared
from shared import run_peru_command, assert_contents


class ReupIntegrationTest(shared.PeruTest):
    def setUp(self):
        self.foo_dir = shared.create_dir({'a': 'b'})
        self.foo_repo = shared.GitRepo(self.foo_dir)
        self.foo_master = self.foo_repo.run('git', 'rev-parse', 'master')
        self.bar_dir = shared.create_dir()
        self.bar_repo = shared.GitRepo(self.bar_dir)
        self.bar_repo.run('git', 'checkout', '-q', '-b', 'otherbranch')
        with open(os.path.join(self.bar_dir, 'barfile'), 'w') as f:
            f.write('new')
        self.bar_repo.run('git', 'add', '-A')
        self.bar_repo.run('git', 'commit', '-m', 'creating barfile')
        self.bar_otherbranch = self.bar_repo.run('git', 'rev-parse',
                                                 'otherbranch')

    def test_single_reup(self):
        yaml_without_imports = dedent('''\
            git module foo:
                url: {}
                rev: master

            git module bar:
                url: {}
                reup: otherbranch
            ''').format(self.foo_dir, self.bar_dir)
        test_dir = shared.create_dir({'peru.yaml': yaml_without_imports})
        expected = dedent('''\
            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
            ''').format(self.foo_dir, self.foo_master, self.bar_dir)
        run_peru_command(['reup', 'foo'], test_dir)
        assert_contents(test_dir, {'peru.yaml': expected}, excludes=['.peru'])

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
        run_peru_command(['reup', 'foo', '--no-sync'], test_dir)
        assert_contents(test_dir, {}, excludes=['.peru', 'peru.yaml'])
        # Now do it with the sync. Note that barfile wasn't pulled in, because
        # we didn't reup bar.
        run_peru_command(['reup', 'foo', '--quiet'], test_dir)
        assert_contents(test_dir, {'a': 'b'}, excludes=['.peru', 'peru.yaml'])

    def test_reup_all(self):
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
        expected = dedent('''\
            imports:
                foo: ./
                bar: ./

            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
                rev: {}
            ''').format(self.foo_dir, self.foo_master, self.bar_dir,
                        self.bar_otherbranch)
        run_peru_command(['reup'], test_dir)
        # This time we finally pull in barfile.
        assert_contents(
            test_dir, {
                'peru.yaml': expected,
                'a': 'b',
                'barfile': 'new'
            },
            excludes=['.peru'])

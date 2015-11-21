import os
import shutil
import textwrap

from peru.compat import makedirs
from peru.runtime import CommandLineError

import shared


class PathsTest(shared.PeruTest):

    def setUp(self):
        self.test_root = shared.create_dir()

        self.project_dir = os.path.join(self.test_root, 'project')
        self.state_dir = os.path.join(self.project_dir, '.peru')
        self.cache_dir = os.path.join(self.state_dir, 'cache')

        self.yaml = textwrap.dedent('''\
            imports:
                foo: ./
            cp module foo:
                # relative paths should always be interpreted from the dir
                # containing peru.yaml, even if that's not the sync dir.
                path: ../foo
            ''')
        shared.write_files(self.project_dir, {'peru.yaml': self.yaml})
        self.peru_file = os.path.join(self.project_dir, 'peru.yaml')

        self.foo_dir = os.path.join(self.test_root, 'foo')
        shared.write_files(self.foo_dir, {'bar': 'baz'})

        # We'll run tests from this inner subdirectory, so that we're more
        # likely to catch places where we're using the cwd incorrectly.
        self.cwd = os.path.join(self.project_dir, 'cwd', 'in', 'here')
        makedirs(self.cwd)

    def assert_success(self, sync_dir, state_dir, cache_dir, more_excludes=[]):
        shared.assert_contents(sync_dir, {'bar': 'baz'},
                               excludes=['.peru', 'peru.yaml'] + more_excludes)
        assert os.path.isfile(os.path.join(state_dir, 'lastimports'))
        assert os.path.isdir(os.path.join(cache_dir, 'trees'))

    def test_unmodified_sync(self):
        shared.run_peru_command(['sync'], self.cwd)
        self.assert_success(self.project_dir, self.state_dir, self.cache_dir)

    def test_peru_file_and_sync_dir_must_be_set_together(self):
        for command in [['--sync-dir=junk', 'sync'],
                        ['--file=junk', 'sync']]:
            with self.assertRaises(CommandLineError):
                shared.run_peru_command(command, cwd=self.cwd)

    def test_file_and_file_basename_incompatible(self):
        with self.assertRaises(CommandLineError):
            shared.run_peru_command(
                ['--file=foo', '--sync-dir=bar', '--file-basename=baz',
                    'sync'],
                cwd=self.cwd)

    def test_setting_all_flags(self):
        cwd = shared.create_dir()
        sync_dir = shared.create_dir()
        state_dir = shared.create_dir()
        cache_dir = shared.create_dir()
        shared.run_peru_command(
            ['--file', self.peru_file, '--sync-dir', sync_dir,
             '--state-dir', state_dir, '--cache-dir', cache_dir, 'sync'],
            cwd)
        self.assert_success(sync_dir, state_dir, cache_dir)

    def test_setting_all_env_vars(self):
        cache_dir = shared.create_dir()
        shared.run_peru_command(['sync'], self.cwd, env={
            'PERU_CACHE_DIR': cache_dir,
        })
        self.assert_success(self.project_dir, self.state_dir, cache_dir)

    def test_flags_override_vars(self):
        flag_cache_dir = shared.create_dir()
        env_cache_dir = shared.create_dir()
        shared.run_peru_command(['--cache-dir', flag_cache_dir, 'sync'],
                                self.cwd,
                                env={'PERU_CACHE_DIR': env_cache_dir})
        self.assert_success(self.project_dir, self.state_dir, flag_cache_dir)

    def test_relative_paths(self):
        '''We ran into a bug where calling os.path.dirname(peru_file) was
        returning "", which got passed as the cwd of a plugin job and blew up.
        This test repros that case. We've switched to pathlib.Path.parent to
        fix the issue.'''
        shared.run_peru_command(
            ['--file', 'peru.yaml', '--sync-dir', '.', 'sync'],
            cwd=self.project_dir)
        self.assert_success(self.project_dir, self.state_dir, self.cache_dir)

    def test_default_file_name(self):
        shutil.move(self.peru_file, os.path.join(self.project_dir, 'xxx'))
        shared.run_peru_command(['--file-basename', 'xxx', 'sync'],
                                cwd=self.cwd)
        self.assert_success(self.project_dir, self.state_dir, self.cache_dir,
                            more_excludes=['xxx'])

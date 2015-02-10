import os
from pathlib import Path
import stat
import textwrap
import unittest

import peru.cache
import peru.compat
import peru.error
import peru.main
from peru.parser import DEFAULT_PERU_FILE_NAME
import peru.rule

import shared
from shared import run_peru_command, assert_contents

PERU_MODULE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(peru.__file__)))


class SyncTest(unittest.TestCase):

    def setUp(self):
        self.test_dir = shared.create_dir()
        self.peru_dir = os.path.join(self.test_dir, '.peru')

    def tearDown(self):
        shared.assert_clean_tmp(self.peru_dir)

    def write_yaml(self, unformatted_yaml, *format_args, dir=None):
        yaml = textwrap.dedent(unformatted_yaml.format(*format_args))
        if dir is None:
            dir = self.test_dir
        with open(os.path.join(dir, DEFAULT_PERU_FILE_NAME), 'w') as f:
            f.write(yaml)

    def do_integration_test(self, args, expected, *, cwd=None,
                            **peru_cmd_kwargs):
        if not cwd:
            cwd = self.test_dir
        run_peru_command(args, cwd, **peru_cmd_kwargs)
        assert_contents(self.test_dir, expected,
                        excludes=[DEFAULT_PERU_FILE_NAME, '.peru'])

    def test_basic_sync(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            ''', module_dir)
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

        # Running it again should be a no-op.
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

        # Running it with a dirty working copy should be an error.
        shared.write_files(self.test_dir, {'subdir/foo': 'dirty'})
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

    def test_sync_from_subdir(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            # Use a relative module path, to make sure it gets resolved
            # relative to the project root and not the dir where peru was
            # called.
            cp module relative_foo:
                path: {}

            imports:
                relative_foo: subdir
            ''', os.path.relpath(module_dir, start=self.test_dir))
        subdir = os.path.join(self.test_dir, 'a', 'b')
        peru.compat.makedirs(subdir)
        run_peru_command(['sync'], subdir)
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, '.peru')),
                        msg=".peru dir didn't end up in the right place")
        assert_contents(os.path.join(self.test_dir, 'subdir'), {'foo': 'bar'})

    def test_conflicting_imports(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {0}

            # same as foo
            cp module bar:
                path: {0}

            imports:
                foo: subdir
                bar: subdir
            ''', module_dir)
        with self.assertRaises(peru.cache.MergeConflictError):
            self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

    def test_empty_imports(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        empty_yaml = '''\
            cp module foo:
                path: {}
            '''.format(module_dir)
        nonempty_yaml = '''\
            cp module foo:
                path: {}
            imports:
                foo: ./
            '''.format(module_dir)
        self.write_yaml(empty_yaml)
        self.do_integration_test(['sync'], {})
        # Now test switching back and forth between non-empty and empty.
        self.write_yaml(nonempty_yaml)
        self.do_integration_test(['sync'], {'foo': 'bar'})
        # Back to empty.
        self.write_yaml(empty_yaml)
        self.do_integration_test(['sync'], {})

    def test_import_module_defined_in_another_module(self):
        # Project B contains project A
        dir_a = shared.create_dir({'afile': 'stuff'})
        dir_b = shared.create_dir()
        # Create the peru.yaml file for B.
        self.write_yaml('''\
            cp module a:
                path: {}
            ''', dir_a, dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml('''\
            imports:
                b.a: a_via_b/

            cp module b:
                path: {}
            ''', dir_b)
        self.do_integration_test(['sync'], {'a_via_b/afile': 'stuff'})
        # Test the error message from an invalid module.
        self.write_yaml('''\
            imports:
                b.missing_module: some_path

            cp module b:
                path: {}
            ''', dir_b)
        try:
            self.do_integration_test(['sync'], {})
        except peru.error.PrintableError as e:
            assert 'b.missing_module' in e.message
        else:
            assert False, 'should throw invalid module error'

    def test_recursive_imports(self):
        # Project B contains project A
        dir_a = shared.create_dir({'afile': 'stuff'})
        dir_b = shared.create_dir()
        # Create the peru.yaml file for B.
        self.write_yaml('''\
            imports:
                a: b_imports/where_b_put_a
            cp module a:
                path: {}
            ''', dir_a, dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml('''\
            imports:
                b: where_c_put_b

            cp module b:
                path: {}
                export: b_imports  # omit the peru.yaml file from b
            ''', dir_b)
        self.do_integration_test(
            ['sync'], {'where_c_put_b/where_b_put_a/afile': 'stuff'})

    def test_peru_file_field(self):
        # Project B contains project A
        dir_a = shared.create_dir({'afile': 'stuff'})
        # Create project B with an unusual YAML filename.
        dir_b = shared.create_dir({'alternate.yaml': textwrap.dedent('''\
            cp module a:
                path: {}
            '''.format(dir_a))})
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml('''\
            imports:
                b.a: a_via_b/

            cp module b:
                path: {}
                peru file: alternate.yaml
            ''', dir_b)
        self.do_integration_test(['sync'], {'a_via_b/afile': 'stuff'})

    def test_module_rules(self):
        module_dir = shared.create_dir({'a/b': '', 'c/d': ''})
        yaml = '''\
            cp module foo:
                path: {}

            rule get_a:
                export: a

            rule get_c:
                export: c

            imports:
                foo|get_a: ./
            '''.format(module_dir)
        self.write_yaml(yaml)
        self.do_integration_test(['sync'], {'b': ''})
        # Run it again with a different import to make sure we clean up.
        yaml_different = yaml.replace('foo|get_a', 'foo|get_c')
        self.write_yaml(yaml_different)
        self.do_integration_test(['sync'], {'d': ''})

    # TODO: Remove these tests when the `files` field is removed.
    def test_rule_with_legacy_files(self):
        content = {name: '' for name in [
            'foo',
            'bar',
            'special',
            'baz/bing',
            'baz/boo/a',
            'baz/boo/b',
        ]}
        module_dir = shared.create_dir(content)
        self.write_yaml('''\
            cp module foo:
                path: {}

            rule filter:
                files:
                  - "**/*oo"
                  - special

            imports:
                foo|filter: ./
            ''', module_dir)
        filtered_content = {name: '' for name in [
            'foo',
            'special',
            'baz/boo/a',
            'baz/boo/b',
        ]}
        self.do_integration_test(['sync'], filtered_content)

    def test_rule_with_legacy_files_that_do_not_exist(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}
                files: idontexist
            imports:
                foo: ./
            ''', module_dir)
        with self.assertRaises(peru.rule.NoMatchingFilesError):
            self.do_integration_test(['sync'], {})

    def test_rule_with_legacy_files_and_picked_files(self):
        content = {name: '' for name in [
            'foo',
            'bar',
            'baz/bing',
            'baz/boo/a',
            'baz/boo/b'
        ]}
        module_dir = shared.create_dir(content)
        self.write_yaml('''\
            cp module foo:
                path: {}

            rule filter:
                pick: baz/bing
                files: boo/*
                export: baz

            imports:
                foo|filter: ./
            ''', module_dir)
        filtered_content = {name: '' for name in [
            'bing',
            'boo/a',
            'boo/b',
        ]}
        self.do_integration_test(['sync'], filtered_content)

    def test_rule_with_picked_files(self):
        content = {name: '' for name in [
            'foo',
            'bar',
            'special',
            'baz/bing',
            'baz/boo/a',
            'baz/boo/b'
        ]}
        module_dir = shared.create_dir(content)
        self.write_yaml('''\
            cp module foo:
                path: {}

            rule filter:
                pick:
                  - "**/*oo"
                  - special

            imports:
                foo|filter: ./
            ''', module_dir)
        filtered_content = {name: '' for name in [
            'foo',
            'special',
            'baz/boo/a',
            'baz/boo/b',
        ]}
        self.do_integration_test(['sync'], filtered_content)

    def test_rule_with_picked_files_that_do_not_exist(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}
                pick: idontexist
            imports:
                foo: ./
            ''', module_dir)
        with self.assertRaises(peru.rule.NoMatchingFilesError) as cm:
            self.do_integration_test(['sync'], {})
        self.assertTrue('No matches for' in cm.exception.message)

    def test_rule_with_picked_files_that_are_not_exported(self):
        content = {name: '' for name in [
            'foo',
            'bar',
            'baz/bing',
            'baz/boo/a',
            'baz/boo/b'
        ]}
        module_dir = shared.create_dir(content)
        self.write_yaml('''\
            cp module foo:
                path: {}
                pick: foo
                export: baz/

            imports:
                foo: ./
            ''', module_dir)
        with self.assertRaises(peru.rule.NoMatchingFilesError) as cm:
            self.do_integration_test(['sync'], {})
        self.assertTrue(
            'none are beneath the export path' in cm.exception.message)

    def test_rule_with_executable(self):
        contents = {'a.txt': '', 'b.txt': '', 'c.foo': ''}
        module_dir = shared.create_dir(contents)
        self.write_yaml('''\
            cp module foo:
                path: {}
                executable: "*.txt"
            imports:
                foo: ./
            ''', module_dir)
        self.do_integration_test(['sync'], contents)
        for f in ('a.txt', 'b.txt'):
            mode = (Path(self.test_dir) / f).stat().st_mode
            assert mode & stat.S_IXUSR
            assert mode & stat.S_IXGRP
            assert mode & stat.S_IXOTH

    def test_rule_with_move(self):
        module_dir = shared.create_dir({'a': 'foo', 'b/c': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}
                move:
                    a: newa
                    b: newb
            imports:
                foo: ./
            ''', module_dir)
        self.do_integration_test(['sync'], {'newa': 'foo', 'newb/c': 'bar'})

    def test_rule_with_move_error(self):
        module_dir = shared.create_dir()
        self.write_yaml('''\
            cp module foo:
                path: {}
                move:
                    doesntexist: also_nonexistent
            imports:
                foo: ./
            ''', module_dir)
        try:
            self.do_integration_test(['sync'],
                                     {'newa': 'foo', 'newb/c': 'bar'})
        except peru.error.PrintableError as e:
            assert 'doesntexist' in e.message

    def test_rule_with_copied_files(self):
        content = {
            'foo': 'foo',
            'bar/baz': 'baz'
        }
        module_dir = shared.create_dir(content)
        self.write_yaml('''\
            cp module foo:
                path: {}
                copy:
                    foo: foo-copy
                    bar:
                      - bar-copy-1
                      - bar-copy-2

            imports:
                foo: ./
            ''', module_dir)
        copied_content = {
            'foo': 'foo',
            'bar/baz': 'baz',
            'foo-copy': 'foo',
            'bar-copy-1/baz': 'baz',
            'bar-copy-2/baz': 'baz'
        }
        self.do_integration_test(['sync'], copied_content)

    def test_alternate_cache(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            ''', module_dir)
        cache_dir = shared.create_dir()
        env_vars = {'PERU_CACHE': cache_dir}
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'},
                                 env_vars=env_vars)
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'plugins')))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'trees')))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'keyval')))
        self.assertFalse(os.path.exists(
            os.path.join(self.peru_dir, 'cache')))

    def test_override(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}

            imports:
                foo: ./
            ''', module_dir)
        override_dir = shared.create_dir({'foo': 'override'})
        # Set the override.
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        # Confirm that the override is configured.
        output = run_peru_command(['override'], self.test_dir)
        self.assertEqual(output, 'foo: {}\n'.format(override_dir))
        # Make sure 'override list' gives the same output as 'override'.
        output = run_peru_command(['override', 'list'], self.test_dir)
        self.assertEqual(output, 'foo: {}\n'.format(override_dir))
        # Run the sync and confirm that the override worked.
        self.do_integration_test(['sync'], {'foo': 'override'})
        # Delete the override.
        run_peru_command(['override', 'delete', 'foo'], self.test_dir)
        # Confirm that the override was deleted.
        output = run_peru_command(['override'], self.test_dir)
        self.assertEqual(output, '')
        # Rerun the sync and confirm the original content is back.
        self.do_integration_test(['sync'], {'foo': 'bar'})

    def test_override_after_regular_sync(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}

            imports:
                foo: ./
            ''', module_dir)
        # First, do a regular sync.
        self.do_integration_test(['sync'], {'foo': 'bar'})
        # Now, add an override, and confirm that the new sync works.
        override_dir = shared.create_dir({'foo': 'override'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        self.do_integration_test(['sync'], {'foo': 'override'})

    def test_relative_override_from_subdir(self):
        self.write_yaml('''\
            empty module foo:

            imports:
                foo: ./
            ''')
        # Create some subdirs inside the project.
        subdir = os.path.join(self.test_dir, 'a', 'b')
        peru.compat.makedirs(subdir)
        # Create an override dir outside the project.
        override_dir = shared.create_dir({'foo': 'override'})
        # Set the override from inside subdir, using the relative path that's
        # valid from that location. Peru is going to store this path in
        # .peru/overrides/ at the root, so this tests that we resolve the
        # stored path properly.
        relative_path = os.path.relpath(override_dir, start=subdir)
        run_peru_command(['override', 'add', 'foo', relative_path],
                         subdir)
        # Confirm that the right path is stored on disk.
        expected_stored_path = os.path.relpath(
            override_dir, start=self.test_dir)
        with open(os.path.join(self.peru_dir, 'overrides', 'foo')) as f:
            actual_stored_path = f.read()
        self.assertEqual(expected_stored_path, actual_stored_path)
        # Confirm that `peru override` prints output that respects the cwd.
        output = run_peru_command(['override'], subdir)
        self.assertEqual('foo: {}\n'.format(relative_path), output)
        # Confirm that syncing works.
        self.do_integration_test(['sync'], {'foo': 'override'}, cwd=subdir)

    def test_override_excludes_dotperu(self):
        self.write_yaml('''\
            empty module foo:

            imports:
                foo: ./
            ''')
        override_dir = shared.create_dir(
            {'foo': 'override', '.peru/bar': 'baz'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        self.do_integration_test(['sync'], {'foo': 'override'})

    def test_rules_in_override(self):
        module_dir = shared.create_dir({'a/b': 'c'})
        yaml = '''
            imports:
                foo|get_a: ./

            cp module foo:
                path: {}

            rule get_a:
                export: a
            '''
        self.write_yaml(yaml, module_dir)
        override_dir = shared.create_dir({'a/b': 'override'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        self.do_integration_test(['sync'], {'b': 'override'})

    def test_copy(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            cp module foo:
                path: {}
            ''', module_dir)
        # Do a simple copy and check the results.
        self.do_integration_test(['copy', 'foo', '.'], {'foo': 'bar'})
        # Running the same copy again should fail, because of conflicts.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(['copy', 'foo', '.'], {'foo': 'bar'})
        # Passing the --force flag should pave over conflicts.
        self.do_integration_test(['copy', '--force', 'foo', '.'],
                                 {'foo': 'bar'})

    def test_copy_nested(self):
        # Project B contains project A
        dir_a = shared.create_dir({'afile': 'stuff'})
        dir_b = shared.create_dir()
        # Create the peru.yaml file for B.
        self.write_yaml('''\
            cp module a:
                path: {}
            ''', dir_a, dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml('''\
            cp module b:
                path: {}
            ''', dir_b)
        self.do_integration_test(['copy', 'b.a', '.'], {'afile': 'stuff'})

    def test_clean(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml('''\
            imports:
                foo: ./
            cp module foo:
                path: {}
            ''', module_dir)
        self.do_integration_test(['clean'], {})
        self.do_integration_test(['sync'], {'foo': 'bar'})
        shared.write_files(self.test_dir, {'foo': 'DIRTY'})
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(['clean'], {})
        self.do_integration_test(['clean', '--force'], {})

    def test_help(self):
        flag_output = run_peru_command(['--help'], self.test_dir)
        self.assertEqual(peru.main.__doc__, flag_output)
        command_output = run_peru_command(['help'], self.test_dir)
        self.assertEqual(peru.main.__doc__, command_output)

    def test_version(self):
        version_output = run_peru_command(["--version"], self.test_dir)
        self.assertEqual(peru.main.get_version(), version_output.strip())

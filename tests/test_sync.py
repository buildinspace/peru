import contextlib
import io
import json
import os
import sys
import textwrap

from peru.async_helpers import raises_gathered
import peru.cache
import peru.compat
import peru.error
import peru.main
from peru.parser import DEFAULT_PERU_FILE_NAME
import peru.rule
import peru.scope

import shared
from shared import run_peru_command, assert_contents

PERU_MODULE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(peru.__file__)))


class SyncTest(shared.PeruTest):
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

    def do_integration_test(self,
                            args,
                            expected,
                            *,
                            cwd=None,
                            **peru_cmd_kwargs):
        if not cwd:
            cwd = self.test_dir
        output = run_peru_command(args, cwd, **peru_cmd_kwargs)
        assert_contents(
            self.test_dir,
            expected,
            excludes=[DEFAULT_PERU_FILE_NAME, '.peru'])
        return output

    def test_basic_sync(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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

    def test_no_cache_flag(self):
        foo_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            ''', foo_dir)

        # Sync the foo module once.
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

        # Change the contents of foo and sync again. Because foo is cached, we
        # shouldn't see any changes.
        shared.write_files(foo_dir, {'foo': 'woo'})
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})

        # Now sync with --no-cache. This time we should see the changes.
        self.do_integration_test(['sync', '--no-cache'], {'subdir/foo': 'woo'})

    def test_sync_from_subdir(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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
        self.assertTrue(
            os.path.isdir(os.path.join(self.test_dir, '.peru')),
            msg=".peru dir didn't end up in the right place")
        assert_contents(os.path.join(self.test_dir, 'subdir'), {'foo': 'bar'})

    def test_conflicting_imports(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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
        self.write_yaml(
            '''\
            cp module a:
                path: {}
            ''',
            dir_a,
            dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml(
            '''\
            imports:
                b.a: a_via_b/

            cp module b:
                path: {}
            ''', dir_b)
        self.do_integration_test(['sync'], {'a_via_b/afile': 'stuff'})
        # Test the error message from an invalid module.
        self.write_yaml(
            '''\
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
        dir_a = shared.create_dir({'afile': 'aaa'})
        dir_b = shared.create_dir({'exports/bfile': 'bbb'})
        # Create the peru.yaml file for B.
        self.write_yaml(
            '''\
            imports:
                a: exports/where_b_put_a
            cp module a:
                path: {}
            ''',
            dir_a,
            dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml(
            '''\
            imports:
                b: where_c_put_b

            cp module b:
                # recursive is false by default
                path: {}
                export: exports  # omit the peru.yaml file from b
            ''', dir_b)
        self.do_integration_test(['sync'], {'where_c_put_b/bfile': 'bbb'})

        # Repeat the same test with explicit 'recursive' settings.
        self.write_yaml(
            '''\
            imports:
                b: where_c_put_b

            cp module b:
                path: {}
                pick: exports/where_b_put_a
                export: exports  # omit the peru.yaml file from b
                recursive: true
            ''', dir_b)
        self.do_integration_test(['sync'],
                                 {'where_c_put_b/where_b_put_a/afile': 'aaa'})

        self.write_yaml(
            '''\
            imports:
                b: where_c_put_b

            cp module b:
                path: {}
                export: exports  # omit the peru.yaml file from b
                recursive: false
            ''', dir_b)
        self.do_integration_test(['sync'], {'where_c_put_b/bfile': 'bbb'})

    def test_recursive_import_error(self):
        '''Errors that happen inside recursively-fetched targets should have
        context information about the targets that caused them. This test is
        especially important for checking that context isn't lost in
        GatheredExceptions.'''
        # Project NOTABLE_NAME has a BAD_MODULE in it.
        dir_notable = shared.create_dir()
        # Create the peru.yaml file for NOTABLE_NAME.
        self.write_yaml(
            '''\
            imports:
                BAD_MODULE: ./
            git module BAD_MODULE:
                bad_field: stuff
                # The error we get here will actually be that `url` is missing.
            ''',
            dir=dir_notable)
        # Now make our test project import it.
        self.write_yaml(
            '''\
            imports:
                NOTABLE_NAME: ./notable

            cp module NOTABLE_NAME:
                recursive: true
                path: {}
            ''', dir_notable)
        with self.assertRaises(peru.error.PrintableError) as cm:
            run_peru_command(['sync'], self.test_dir)
        self.assertIn("NOTABLE_NAME", cm.exception.message)
        self.assertIn("BAD_MODULE", cm.exception.message)

    def test_peru_file_field(self):
        # Project B contains project A
        dir_a = shared.create_dir({'afile': 'stuff'})
        # Create project B with an unusual YAML filename.
        dir_b = shared.create_dir({
            'alternate.yaml':
            textwrap.dedent('''\
            cp module a:
                path: {}
            '''.format(dir_a))
        })
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml(
            '''\
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

    def test_rule_with_picked_files(self):
        content = {
            name: ''
            for name in
            ['foo', 'bar', 'special', 'baz/bing', 'baz/boo/a', 'baz/boo/b']
        }
        module_dir = shared.create_dir(content)
        self.write_yaml(
            '''\
            cp module foo:
                path: {}

            rule filter:
                pick:
                  - "**/*oo"
                  - special

            imports:
                foo|filter: ./
            ''', module_dir)
        filtered_content = {
            name: ''
            for name in [
                'foo',
                'special',
                'baz/boo/a',
                'baz/boo/b',
            ]
        }
        self.do_integration_test(['sync'], filtered_content)

    def test_rule_with_picked_files_that_do_not_exist(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
            cp module foo:
                path: {}
                pick: idontexist
            imports:
                foo: ./
            ''', module_dir)
        with raises_gathered(peru.rule.NoMatchingFilesError):
            self.do_integration_test(['sync'], {})

    def test_rule_with_exported_files_that_are_not_picked(self):
        content = {
            name: ''
            for name in ['foo', 'bar', 'baz/bing', 'baz/boo/a', 'baz/boo/b']
        }
        module_dir = shared.create_dir(content)
        self.write_yaml(
            '''\
            cp module foo:
                path: {}
                pick: foo
                export: baz/

            imports:
                foo: ./
            ''', module_dir)
        with raises_gathered(peru.rule.NoMatchingFilesError):
            self.do_integration_test(['sync'], {})

    def test_rule_with_dropped_files(self):
        content = {'foo': 'one', 'bar': 'two'}
        module_dir = shared.create_dir(content)
        self.write_yaml(
            '''\
            cp module foobar:
                path: {}

            rule filter:
                drop: foo

            imports:
                foobar|filter: ./
            ''', module_dir)
        filtered_content = {'bar': 'two'}
        self.do_integration_test(['sync'], filtered_content)

    def test_drop_then_pick_is_an_error(self):
        '''We want drop to run before pick, so that deleting a bunch of stuff
        and then trying to pick it turns into an error. The opposite execution
        order would make this silently succeed. See the discussion at
        https://github.com/buildinspace/peru/issues/150#issuecomment-212580912.
        '''
        content = {'foo': 'stuff'}
        module_dir = shared.create_dir(content)
        self.write_yaml(
            '''\
            cp module foobar:
                path: {}
                drop: foo
                pick: foo

            imports:
                foobar: ./
            ''', module_dir)
        with raises_gathered(peru.rule.NoMatchingFilesError):
            run_peru_command(['sync'], self.test_dir)

    def test_rule_with_executable(self):
        contents = {'a.txt': '', 'b.txt': '', 'c.foo': ''}
        module_dir = shared.create_dir(contents)
        self.write_yaml(
            '''\
            cp module foo:
                path: {}
                executable: "*.txt"
            imports:
                foo: ./
            ''', module_dir)
        self.do_integration_test(['sync'], contents)
        for f in ('a.txt', 'b.txt'):
            shared.assert_executable(os.path.join(self.test_dir, f))

    def test_rule_with_move(self):
        module_dir = shared.create_dir({'a': 'foo', 'b/c': 'bar'})
        self.write_yaml(
            '''\
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
        self.write_yaml(
            '''\
            cp module foo:
                path: {}
                move:
                    doesntexist: also_nonexistent
            imports:
                foo: ./
            ''', module_dir)
        with raises_gathered(peru.rule.NoMatchingFilesError) as cm:
            self.do_integration_test(['sync'], {
                'newa': 'foo',
                'newb/c': 'bar'
            })
        assert 'doesntexist' in cm.exception.message

    def test_rule_with_copied_files(self):
        content = {'foo': 'foo', 'bar/baz': 'baz'}
        module_dir = shared.create_dir(content)
        self.write_yaml(
            '''\
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
        self.write_yaml(
            '''\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            ''', module_dir)
        cache_dir = shared.create_dir()
        env = {'PERU_CACHE_DIR': cache_dir}
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'}, env=env)
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'plugins')))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'trees')))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, 'keyval')))
        self.assertFalse(os.path.exists(os.path.join(self.peru_dir, 'cache')))

    def test_override(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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
        # Same as above, but as JSON (with --json flag).
        output = run_peru_command(['override', '--json'], self.test_dir)
        override_dict = json.loads(output)
        self.assertEqual(override_dict, {'foo': override_dir})
        # Run the sync with --no-overrides and confirm nothing changes. Also
        # check that there's no overrides-related output.
        output = self.do_integration_test(['sync', '--no-overrides'],
                                          {'foo': 'bar'})
        self.assertNotIn('overrides', output)
        # Now run the sync normally and confirm that the override worked. Also
        # confirm that we mentioned the override in output, and that the unused
        # overrides warning is not printed.
        output = self.do_integration_test(['sync'], {'foo': 'override'})
        self.assertIn('overrides', output)
        self.assertNotIn('WARNING unused overrides', output)
        # Delete the override.
        run_peru_command(['override', 'delete', 'foo'], self.test_dir)
        # Confirm that the override was deleted.
        output = run_peru_command(['override'], self.test_dir)
        self.assertEqual(output, '')
        # Rerun the sync and confirm the original content is back.
        self.do_integration_test(['sync'], {'foo': 'bar'})
        # Add a bogus override and confirm the unused overrides warning is
        # printed.
        run_peru_command(['override', 'add', 'bogus', override_dir],
                         self.test_dir)
        output = self.do_integration_test(['sync'], {'foo': 'bar'})
        self.assertIn('WARNING unused overrides', output)

    def test_override_after_regular_sync(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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

    def test_override_recursive(self):
        # Module A just includes the file 'foo'.
        module_a_dir = shared.create_dir({'foo': 'bar'})
        # Module B imports module A.
        module_b_dir = shared.create_dir()
        self.write_yaml(
            '''\
            cp module A:
                path: {}

            imports:
                A: A/
            ''',
            module_a_dir,
            dir=module_b_dir)
        # Module C (in self.test_dir) imports module B, and also directly
        # imports module A. When we set an override for module A below, we'll
        # want to check that *both* of these imports get overridden.
        self.write_yaml(
            '''\
            cp module B:
                path: {}
                recursive: true
                # Note that module business happens before rule business, so
                # 'drop: peru.yaml' will not affect the recursion, just the
                # final output.
                drop: peru.yaml

            imports:
                B.A: A/
                B: B/
            ''', module_b_dir)
        # First, do a regular sync.
        self.do_integration_test(['sync'], {
            'A/foo': 'bar',
            'B/A/foo': 'bar',
        })
        # Now set an override for B.A.
        override_dir = shared.create_dir({'foo': 'override'})
        run_peru_command(['override', 'add', 'B.A', override_dir],
                         self.test_dir)
        # Now do another sync. *Both* the directly imported copy of A *and* the
        # copy synced inside of B should be overridden.
        self.do_integration_test(['sync'], {
            'A/foo': 'override',
            'B/A/foo': 'override',
        })

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
        run_peru_command(['override', 'add', 'foo', relative_path], subdir)
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
        override_dir = shared.create_dir({
            'foo': 'override',
            '.peru/bar': 'baz'
        })
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

    def test_missing_name_errors(self):
        self.write_yaml('''
            imports:
                thingabc: path
            ''')
        with self.assertRaises(peru.error.PrintableError) as cm:
            self.do_integration_test(['sync'], {})
        assert "thingabc" in cm.exception.message
        self.write_yaml('''
            imports:
                thingabc|rulexyz: path

            git module thingabc:
                url: http://example.com
            ''')
        with self.assertRaises(peru.error.PrintableError) as cm:
            self.do_integration_test(['sync'], {})
        assert "rulexyz" in cm.exception.message, cm.exception.message

    def test_copy(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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
        self.write_yaml(
            '''\
            cp module a:
                path: {}
            ''',
            dir_a,
            dir=dir_b)
        # Now create the peru.yaml file in the actual test project.
        self.write_yaml(
            '''\
            cp module b:
                path: {}
            ''', dir_b)
        self.do_integration_test(['copy', 'b.a', '.'], {'afile': 'stuff'})

    def test_clean(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
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

        clean_help = peru.main.COMMAND_DOCS['clean']

        pre_flag_output = run_peru_command(['-h', 'clean'], self.test_dir)
        self.assertEqual(clean_help, pre_flag_output)

        post_flag_output = run_peru_command(['clean', '-h'], self.test_dir)
        self.assertEqual(clean_help, post_flag_output)

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            run_peru_command(['foobarbaz'], self.test_dir, expected_error=1)
        self.assertEqual(peru.main.__doc__, buffer.getvalue())

    def test_version(self):
        version_output = run_peru_command(["--version"], self.test_dir)
        self.assertEqual(peru.main.get_version(), version_output.strip())

    def test_duplicate_keys_warning(self):
        self.write_yaml('''\
            git module foo:
            git module foo:
            ''')
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            run_peru_command(['sync'], self.test_dir)
        assert ('WARNING' in buffer.getvalue())
        assert ('git module foo' in buffer.getvalue())
        # Make sure --quiet suppresses the warning.
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            run_peru_command(['sync', '--quiet'], self.test_dir)
        # Don't literally check that stderr is empty, because that could get
        # tripped up on other Python warnings (like asyncio taking too long).
        assert 'git module foo' not in buffer.getvalue()

    def test_lastimports_timestamp(self):
        module_dir = shared.create_dir({'foo': 'bar'})
        template = '''\
            cp module foo:
                path: {}

            imports:
                foo: {}
            '''
        self.write_yaml(template, module_dir, "subdir1")
        self.do_integration_test(['sync'], {'subdir1/foo': 'bar'})
        lastimports = os.path.join(self.test_dir, '.peru', 'lastimports')

        def get_timestamp():
            return os.stat(lastimports).st_mtime

        original_timestamp = get_timestamp()

        # Running it again should be a no-op. Assert that the lastimports
        # timestamp hasn't changed.
        self.do_integration_test(['sync'], {'subdir1/foo': 'bar'})
        assert get_timestamp() == original_timestamp, \
            "Expected an unchanged timestamp."

        # Modify peru.yaml and sync again. This should change the timestamp.
        self.write_yaml(template, module_dir, "subdir2")
        self.do_integration_test(['sync'], {'subdir2/foo': 'bar'})
        assert get_timestamp() > original_timestamp, \
            "Expected an updated timestamp."

    def test_number_of_git_commands(self):
        '''A no-op sync should be a single git command. Also check that index
        files are deleted after any sync error.'''
        module_dir = shared.create_dir({'foo': 'bar'})
        self.write_yaml(
            '''\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            ''', module_dir)
        index_path = os.path.join(self.test_dir, '.peru/lastimports.index')

        # The first sync should take multiple operations and create a
        # lastimports.index file.
        peru.cache.DEBUG_GIT_COMMAND_COUNT = 0
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})
        assert peru.cache.DEBUG_GIT_COMMAND_COUNT > 1, \
            'The first sync should take multiple operations.'
        assert os.path.exists(index_path), \
            'The first sync should create an index file.'

        # The second sync should reuse the index file and only take one
        # operation.
        peru.cache.DEBUG_GIT_COMMAND_COUNT = 0
        self.do_integration_test(['sync'], {'subdir/foo': 'bar'})
        assert peru.cache.DEBUG_GIT_COMMAND_COUNT == 1, \
            'The second sync should take only one operation.'
        assert os.path.exists(index_path), \
            'The second sync should preserve the index file.'

        # Now force an error. This should delete the index file.
        with open(os.path.join(self.test_dir, 'subdir/foo'), 'w') as f:
            f.write('dirty')
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            run_peru_command(['sync'], self.test_dir)
        assert not os.path.exists(index_path), \
            'The error should delete the index file.'

        # Fix the error and resync with new module contents. This should
        # recreate the index file with the current tree and then succeed,
        # rather than using an empty index and treating the current files as
        # conflicting.
        with open(os.path.join(self.test_dir, 'subdir/foo'), 'w') as f:
            f.write('bar')
        with open(os.path.join(module_dir, 'foo'), 'w') as f:
            f.write('new bar')
        self.do_integration_test(['sync', '--no-cache'],
                                 {'subdir/foo': 'new bar'})
        assert os.path.exists(index_path), \
            'The index should have been recreated.'

    def test_module_list(self):
        self.write_yaml('''\
            git module foo:
                url: blah
            git module bar:
                url: blah
            ''')

        output = run_peru_command(['module'], self.test_dir)
        self.assertEqual(output, "bar\nfoo\n")

        output = run_peru_command(['module', 'list'], self.test_dir)
        self.assertEqual(output, "bar\nfoo\n")

        output = run_peru_command(['module', 'list', '--json'], self.test_dir)
        self.assertEqual(output, '["bar", "foo"]\n')


@contextlib.contextmanager
def redirect_stderr(f):
    old_stderr = sys.stderr
    sys.stderr = f
    try:
        yield
    finally:
        sys.stderr = old_stderr

import os
from textwrap import dedent
import unittest

import peru.cache
import peru.compat
import peru.error
import peru.main
import peru.rule

import shared
from shared import run_peru_command, assert_contents

PERU_MODULE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(peru.__file__)))


class SyncTest(unittest.TestCase):

    def setUp(self):
        self.module_dir = shared.create_dir({
            "foo": "bar",
        })
        self.test_dir = shared.create_dir()
        self.peru_dir = os.path.join(self.test_dir, '.peru')

    def tearDown(self):
        shared.assert_clean_tmp(self.peru_dir)

    def write_peru_yaml(self, template):
        peru_yaml = dedent(template.format(self.module_dir))
        shared.write_files(self.test_dir, {'peru.yaml': peru_yaml})

    def do_integration_test(self, args, expected, cwd=None, **kwargs):
        if not cwd:
            cwd = self.test_dir
        run_peru_command(args, cwd, **kwargs)
        assert_contents(self.test_dir, expected,
                        excludes=['peru.yaml', '.peru'])

    def test_basic_sync(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            """)
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})

        # Running it again should be a no-op.
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})

        # Running it with a dirty working copy should be an error.
        shared.write_files(self.test_dir, {'subdir/foo': 'dirty'})
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"})

    def test_sync_from_subdir(self):
        peru_yaml = dedent('''\
            # Use a relative module path, to make sure it gets resolved
            # relative to the project root and not the dir where peru was
            # called.
            cp module relative_foo:
                path: {}

            imports:
                relative_foo: subdir
            '''.format(os.path.relpath(self.module_dir, start=self.test_dir)))
        shared.write_files(self.test_dir, {'peru.yaml': peru_yaml})
        subdir = os.path.join(self.test_dir, 'a', 'b')
        peru.compat.makedirs(subdir)
        run_peru_command(['sync'], subdir)
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, '.peru')),
                        msg=".peru dir didn't end up in the right place")
        assert_contents(os.path.join(self.test_dir, 'subdir'), {'foo': 'bar'})

    def test_conflicting_imports(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {0}

            # same as foo
            cp module bar:
                path: {0}

            imports:
                foo: subdir
                bar: subdir
            """)
        with self.assertRaises(peru.cache.MergeConflictError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"})

    def test_empty_imports(self):
        self.write_peru_yaml('''\
            cp module foo:
                path: {0}
            ''')
        self.do_integration_test(['sync'], {})
        # Now test switching back and forth between non-empty and empty.
        self.write_peru_yaml('''\
            cp module foo:
                path: {0}
            imports:
                foo: ./
            ''')
        self.do_integration_test(['sync'], {'foo': 'bar'})
        # Back to empty.
        self.write_peru_yaml('''\
            cp module foo:
                path: {0}
            ''')
        self.do_integration_test(['sync'], {})

    @unittest.skipIf(os.name == 'nt', 'build commands not Windows-compatible')
    def test_module_rules(self):
        template = """\
            cp module foo:
                path: {}
                build: printf 2 >> foo; mkdir baz; mv foo baz
                export: baz

            rule copy1:
                build: cp foo copy1

            rule copy2:
                build: cp foo copy2

            imports:
                foo|copy1: ./
            """
        self.write_peru_yaml(template)
        self.do_integration_test(["sync"], {"foo": "bar2", "copy1": "bar2"})
        # Run it again with a different import to make sure we clean up.
        template = template.replace("foo|copy1", "foo|copy2")
        self.write_peru_yaml(template)
        self.do_integration_test(["sync"], {"foo": "bar2", "copy2": "bar2"})

    @unittest.skipIf(os.name == 'nt', 'build commands not Windows-compatible')
    def test_build_output(self):
        # Make sure build commands are sending their output to the display like
        # they're supposed do. This also has the effect of testing that modules
        # and rules are cached like they're supposed to be -- if not, they'll
        # show up in the output more than once.
        self.write_peru_yaml('''\
            imports:
                basic: dir1/
                basic|complicated: dir2/

            cp module basic:
                path: {}
                build: echo foo

            rule complicated:
                build: echo bar
            ''')
        expected_output = dedent('''\
            === started basic ===
            === finished basic ===
            foo
            bar
            ''')
        output = run_peru_command(['sync', '-v'], self.test_dir)
        self.assertEqual(expected_output, output)

    def test_rule_with_files(self):
        content = {name: '' for name in [
            'foo',
            'bar',
            'special',
            'baz/bing',
            'baz/boo/a',
            'baz/boo/b',
        ]}
        self.module_dir = shared.create_dir(content)
        self.write_peru_yaml('''\
            cp module foo:
                path: {}

            rule filter:
                files:
                  - "**/*oo"
                  - special

            imports:
                foo|filter: ./
            ''')
        filtered_content = {name: '' for name in [
            'foo',
            'special',
            'baz/boo/a',
            'baz/boo/b',
        ]}
        self.do_integration_test(['sync'], filtered_content)

    def test_rule_with_files_that_dont_match(self):
        self.write_peru_yaml('''\
            cp module foo:
                path: {}
                files: idontexist
            imports:
                foo: ./
            ''')
        with self.assertRaises(peru.rule.NoMatchingFilesError):
            self.do_integration_test(['sync'], {})

    def test_alternate_cache(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            """)
        cache_dir = shared.create_dir()
        env_vars = {"PERU_CACHE": cache_dir}
        self.do_integration_test(["sync"], {"subdir/foo": "bar"},
                                 env_vars=env_vars)
        self.assertTrue(os.path.exists(os.path.join(cache_dir, "plugins")))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, "trees")))
        self.assertTrue(os.path.exists(os.path.join(cache_dir, "keyval")))
        self.assertFalse(os.path.exists(
            os.path.join(self.peru_dir, "cache")))

    override_test_yaml = '''\
        # module x is for testing imports in the overridden module foo
        empty module x:
            build: printf x > x

        cp module foo:
            path: {}
            build: mkdir -p subdir && mv foo subdir/builtfoo
            export: subdir

        # Test that this rule gets run in the right place (e.g. in the
        # export dir) even when the foo module is overridden.
        rule bang:
            build: printf '!' >> builtfoo

        imports:
            foo|bang: ./
        '''

    @unittest.skipIf(os.name == 'nt', 'build commands not Windows-compatible')
    def test_override(self):
        self.write_peru_yaml(self.override_test_yaml)
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
        self.do_integration_test(['sync'], {'builtfoo': 'override!'})
        # Delete the override.
        run_peru_command(['override', 'delete', 'foo'], self.test_dir)
        # Confirm that the override was deleted.
        output = run_peru_command(['override'], self.test_dir)
        self.assertEqual(output, '')
        # Rerun the sync and confirm the original content is back.
        self.do_integration_test(['sync'], {'builtfoo': 'bar!'})

    @unittest.skipIf(os.name == 'nt', 'build commands not Windows-compatible')
    def test_override_after_regular_sync(self):
        self.write_peru_yaml(self.override_test_yaml)
        # First, do a regular sync.
        self.do_integration_test(['sync'], {'builtfoo': 'bar!'})
        # Now, add an override, and confirm that the new sync works.
        override_dir = shared.create_dir({'foo': 'override'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        self.do_integration_test(['sync'], {'builtfoo': 'override!'})

    def test_relative_override_from_subdir(self):
        self.write_peru_yaml('''\
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
        with open(os.path.join(self.peru_dir, "overrides", "foo")) as f:
            actual_stored_path = f.read()
        self.assertEqual(expected_stored_path, actual_stored_path)
        # Confirm that `peru override` prints output that respects the cwd.
        output = run_peru_command(['override'], subdir)
        self.assertEqual("foo: {}\n".format(relative_path), output)
        # Confirm that syncing works.
        self.do_integration_test(['sync'], {'foo': 'override'}, cwd=subdir)

    def test_override_excludes_dotperu(self):
        self.write_peru_yaml('''\
            empty module foo:

            imports:
                foo: ./
            ''')
        override_dir = shared.create_dir(
            {'foo': 'override', '.peru/bar': 'baz'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)
        self.do_integration_test(['sync'], {'foo': 'override'})

    @unittest.skipIf(os.name == 'nt', 'build commands not Windows-compatible')
    def test_rules_in_override(self):
        def _write_peru_yaml(target):
            self.write_peru_yaml('''\
                imports:
                    TARGET: ./

                cp module foo:
                    path: {}

                rule test_build:
                    build: |
                        printf fee >> fi
                        mkdir -p subdir
                        printf fo >> subdir/fum

                rule test_export:
                    export: subdir
                '''.replace('TARGET', target))

        _write_peru_yaml('foo|test_build')
        override_dir = shared.create_dir()
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir)

        # Syncing against a build rule should build in the override.
        self.do_integration_test(['sync'], {'fi': 'fee', 'subdir/fum': 'fo'})

        # Another sync should run the build again.
        self.do_integration_test(
            ['sync'], {'fi': 'feefee', 'subdir/fum': 'fofo'})

        # Make sure export dirs are respected in rules that come after.
        _write_peru_yaml('foo|test_build|test_export|test_build')
        self.do_integration_test(
            ['sync'], {'fum': 'fofofo', 'fi': 'fee', 'subdir/fum': 'fo'})

    def test_copy(self):
        self.write_peru_yaml('''\
            cp module foo:
                path: {}
            ''')
        # Do a simple copy and check the results.
        self.do_integration_test(['copy', 'foo', '.'], {'foo': 'bar'})
        # Running the same copy again should fail, because of conflicts.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(['copy', 'foo', '.'], {'foo': 'bar'})
        # Passing the --force flag should pave over conflicts.
        self.do_integration_test(['copy', '--force', 'foo', '.'],
                                 {'foo': 'bar'})

    def test_clean(self):
        self.write_peru_yaml('''\
            imports:
                foo: ./
            cp module foo:
                path: {}
            ''')
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

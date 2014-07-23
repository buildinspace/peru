import io
import os
import shutil
import sys
from textwrap import dedent
import unittest

import peru.cache
import peru.compat
import peru.error
import peru.main
import peru.rule

import shared

PERU_MODULE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(peru.__file__)))


def run_peru_command(args, test_dir, peru_dir, *, env_vars=None,
                     capture_stdout=False):
    # Specifying PERU_DIR keeps peru files from cluttering the expected
    # outputs.
    env = env_vars.copy() if env_vars else {}
    if peru_dir:
        env["PERU_DIR"] = peru_dir
    old_cwd = os.getcwd()
    old_stdout = sys.stdout
    os.chdir(test_dir)
    if capture_stdout:
        capture_stream = io.StringIO()
        sys.stdout = capture_stream
    try:
        # Rather than invoking peru as a subprocess, just call directly into
        # the Main class. This lets us check that the right types of exceptions
        # make it up to the top, so we don't need to check specific outputs
        # strings.
        peru.main.Main().run(args, env)
    finally:
        os.chdir(old_cwd)
        sys.stdout = old_stdout
    if capture_stdout:
        return capture_stream.getvalue()


class IntegrationTest(unittest.TestCase):

    def setUp(self):
        self.module_dir = shared.create_dir({
            "foo": "bar",
        })
        self.peru_dir = shared.create_dir()
        self.test_dir = shared.create_dir()

    def tearDown(self):
        # Make sure that everything in the tmp dirs has been cleaned up.
        tmp_root = os.path.join(self.peru_dir, "tmp")
        if os.path.exists(tmp_root):
            tmpfiles = os.listdir(tmp_root)
            self.assertListEqual([], tmpfiles, msg="main tmp dir is not clean")
        cache_tmp_root = os.path.join(self.peru_dir, "cache", "tmp")
        if os.path.exists(cache_tmp_root):
            tmpfiles = os.listdir(cache_tmp_root)
            self.assertListEqual([], tmpfiles,
                                 msg="cache tmp dir is not clean")

    def write_peru_yaml(self, template):
        self.peru_yaml = dedent(template.format(self.module_dir))
        shared.write_files(self.test_dir, {'peru.yaml': self.peru_yaml})

    def do_integration_test(self, args, expected, cwd=None, **kwargs):
        if not cwd:
            cwd = self.test_dir
        run_peru_command(args, cwd, self.peru_dir, **kwargs)
        expected_with_yaml = expected.copy()
        expected_with_yaml["peru.yaml"] = self.peru_yaml
        self.assertDictEqual(expected_with_yaml,
                             shared.read_dir(self.test_dir))

    def test_basic_sync(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            """)
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})
        self.assertTrue(
            os.path.exists(os.path.join(
                self.peru_dir, "cache", "plugins", "cp")),
            msg="Plugin cache should be written to the right place.")

        # Running it again should be a no-op.
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})

        # Running it with a dirty working copy should be an error.
        shared.write_files(self.test_dir, {'subdir/foo': 'dirty'})
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"})

    def test_sync_from_subdir(self):
        self.peru_yaml = dedent('''\
            # Use a relative module path, to make sure it gets resolved
            # relative to the project root and not the dir where peru was
            # called.
            cp module relative_foo:
                path: {}

            imports:
                relative_foo: subdir
            '''.format(os.path.relpath(self.module_dir, start=self.test_dir)))
        shared.write_files(self.test_dir, {'peru.yaml': self.peru_yaml})
        subdir = os.path.join(self.test_dir, 'a', 'b')
        peru.compat.makedirs(subdir)
        run_peru_command(['sync'], subdir, peru_dir=None)
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, '.peru')),
                        msg=".peru dir didn't end up in the right place")
        actual_content = shared.read_dir(os.path.join(self.test_dir, 'subdir'))
        self.assertDictEqual({'foo': 'bar'}, actual_content)

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
                foo:copy1: ./
            """
        self.write_peru_yaml(template)
        self.do_integration_test(["sync"], {"foo": "bar2", "copy1": "bar2"})
        # Run it again with a different import to make sure we clean up.
        template = template.replace("foo:copy1", "foo:copy2")
        self.write_peru_yaml(template)
        self.do_integration_test(["sync"], {"foo": "bar2", "copy2": "bar2"})

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
                foo:filter: ./
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

    def test_local_build(self):
        self.write_peru_yaml("""\
            imports:
                foo: subdir

            build: printf hi >> lo

            cp module foo:
                path: {}

            rule local_build:
                build: printf fee >> fi
            """)

        # Calling build with no arguments should run just the default rule.
        self.do_integration_test(["build"], {
            "subdir/foo": "bar",
            "lo": "hi",
        })
        # Calling build again should run the default rule again.
        self.do_integration_test(["build"], {
            "subdir/foo": "bar",
            "lo": "hihi",
        })
        # Now call it with arguments, which should run the default rule a third
        # time in addition to the rules given.
        self.do_integration_test(["build", "local_build", "local_build"], {
            "subdir/foo": "bar",
            "lo": "hihihi",
            "fi": "feefee",
        })

    def test_local_plugins(self):
        cp_plugin_path = os.path.join(
            PERU_MODULE_ROOT, 'resources', 'plugins', 'cp')
        shutil.copytree(cp_plugin_path,
                        os.path.join(self.test_dir, 'myplugins', 'newfangled'))
        # Grab the contents now so that we can match it later.
        # TODO: Rethink how these tests are structured.
        expected_content = shared.read_dir(self.test_dir)
        expected_content['foo'] = 'bar'

        self.write_peru_yaml('''\
            imports:
                foo: ./

            plugins: myplugins/

            newfangled module foo:
                path: {}
            ''')
        self.do_integration_test(['sync'], expected_content)

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
            imports:
                x: subdir
            build: mv foo subdir/builtfoo
            export: subdir

        # Test that this rule gets run in the right place (e.g. in the
        # export dir) even when the foo module is overridden.
        rule bang:
            build: printf '!' >> builtfoo

        imports:
            foo:bang: ./
        '''

    def test_override(self):
        self.write_peru_yaml(self.override_test_yaml)
        override_dir = shared.create_dir({'foo': 'override'})
        # Set the override.
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir, self.peru_dir)
        # Confirm that the override is configured.
        output = run_peru_command(['override'], self.test_dir, self.peru_dir,
                                  capture_stdout=True)
        self.assertEqual(output, 'foo: {}\n'.format(override_dir))
        # Run the sync and confirm that the override worked.
        self.do_integration_test(['sync'], {'builtfoo': 'override!', 'x': 'x'})
        # Delete the override.
        run_peru_command(['override', 'delete', 'foo'], self.test_dir,
                         self.peru_dir)
        # Confirm that the override was deleted.
        output = run_peru_command(['override'], self.test_dir, self.peru_dir,
                                  capture_stdout=True)
        self.assertEqual(output, '')
        # Rerun the sync and confirm the original content is back.
        self.do_integration_test(['sync'], {'builtfoo': 'bar!', 'x': 'x'})

    def test_override_after_regular_sync(self):
        self.write_peru_yaml(self.override_test_yaml)
        # First, do a regular sync.
        self.do_integration_test(['sync'], {'builtfoo': 'bar!', 'x': 'x'})
        # Now, add an override, and confirm that the new sync works.
        override_dir = shared.create_dir({'foo': 'override'})
        run_peru_command(['override', 'add', 'foo', override_dir],
                         self.test_dir, self.peru_dir)
        self.do_integration_test(['sync'], {'builtfoo': 'override!', 'x': 'x'})

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
                         subdir, self.peru_dir)
        # Confirm that the right path is stored on disk.
        expected_stored_path = os.path.relpath(
            override_dir, start=self.test_dir)
        with open(os.path.join(self.peru_dir, "overrides", "foo")) as f:
            actual_stored_path = f.read()
        self.assertEqual(expected_stored_path, actual_stored_path)
        # Confirm that `peru override` prints output that respects the cwd.
        output = run_peru_command(['override'], subdir, self.peru_dir,
                                  capture_stdout=True)
        self.assertEqual("foo: {}\n".format(relative_path), output)
        # Confirm that syncing works.
        self.do_integration_test(['sync'], {'foo': 'override'}, cwd=subdir)

    def test_export(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}
            """)
        # Do a simple export and check the results.
        self.do_integration_test(["export", "foo", "."], {"foo": "bar"})
        # Running the same export again should fail, because of conflicts.
        with self.assertRaises(peru.cache.DirtyWorkingCopyError):
            self.do_integration_test(["export", "foo", "."], {"foo": "bar"})
        # Passing the --force flag should pave over conflicts.
        self.do_integration_test(["export", "--force", "foo", "."],
                                 {"foo": "bar"})

    def test_help(self):
        flag_output = run_peru_command(['--help'], self.test_dir,
                                       self.peru_dir, capture_stdout=True)
        self.assertEqual(peru.main.__doc__, flag_output)
        command_output = run_peru_command(['help'], self.test_dir,
                                          self.peru_dir, capture_stdout=True)
        self.assertEqual(peru.main.__doc__, command_output)

    def test_version(self):
        version_output = run_peru_command(["--version"], self.test_dir,
                                          self.peru_dir, capture_stdout=True)
        self.assertEqual(peru.main.__version__, version_output.strip())


class ReupIntegrationTest(unittest.TestCase):
    def setUp(self):
        template = dedent("""\
            git module foo:
                url: {}
                rev: master

            git module bar:
                url: {}
                reup: otherbranch
            """)
        self.foo_dir = shared.create_dir()
        self.foo_repo = shared.GitRepo(self.foo_dir)
        self.foo_master = self.foo_repo.run("git rev-parse master")
        self.bar_dir = shared.create_dir()
        self.bar_repo = shared.GitRepo(self.bar_dir)
        self.bar_repo.run("git checkout -q -b otherbranch")
        self.bar_repo.run("git commit --allow-empty -m junk")
        self.bar_otherbranch = self.bar_repo.run("git rev-parse otherbranch")
        self.start_yaml = template.format(self.foo_dir, self.bar_dir)
        self.test_dir = shared.create_dir({"peru.yaml": self.start_yaml})
        self.peru_dir = shared.create_dir()

    def do_integration_test(self, args, expected_yaml, **kwargs):
        run_peru_command(args, self.test_dir, self.peru_dir, **kwargs)
        self.assertDictEqual({"peru.yaml": expected_yaml},
                             shared.read_dir(self.test_dir))

    def test_single_reup(self):
        expected = dedent("""\
            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
            """).format(self.foo_dir, self.foo_master, self.bar_dir)
        self.do_integration_test(["reup", "foo", "--quiet"], expected)

    def test_reup_all(self):
        expected = dedent("""\
            git module foo:
                url: {}
                rev: {}

            git module bar:
                url: {}
                reup: otherbranch
                rev: {}
            """).format(self.foo_dir, self.foo_master, self.bar_dir,
                        self.bar_otherbranch)
        self.do_integration_test(["reup", "--all", "--quiet"], expected)

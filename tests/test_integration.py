import io
import os
import sys
from textwrap import dedent
import unittest

import peru.cache
import peru.main
import peru.error
import peru.override

import shared

peru_bin = os.path.join(os.path.dirname(__file__), "..", "..", "peru.sh")


def run_peru_command(args, test_dir, peru_dir, *, env_vars=None,
                     capture_stdout=False):
    # Specifying PERU_DIR keeps peru files from cluttering the expected
    # outputs.
    env = env_vars.copy() if env_vars else {}
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
        # Make sure that everything in the cache tmp dir has been cleaned up.
        cache_tmp_dir_path = os.path.join(self.peru_dir, "cache", "tmp")
        if os.path.exists(cache_tmp_dir_path):
            tmpfiles = os.listdir(cache_tmp_dir_path)
            self.assertListEqual([], tmpfiles, msg="tmp dir is not clean")

    def write_peru_yaml(self, template):
        self.peru_yaml = dedent(template.format(self.module_dir))
        with open(os.path.join(self.test_dir, "peru.yaml"), "w") as f:
            f.write(self.peru_yaml)

    def do_integration_test(self, args, expected, **kwargs):
        run_peru_command(args, self.test_dir, self.peru_dir, **kwargs)
        expected_with_yaml = expected.copy()
        expected_with_yaml["peru.yaml"] = self.peru_yaml
        self.assertDictEqual(expected_with_yaml,
                             shared.read_dir(self.test_dir))

    def test_basic_import(self):
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
        with open(os.path.join(self.test_dir, "subdir", "foo"), "w") as f:
            f.write("dirty")
        with self.assertRaises(peru.error.PrintableError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"})

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
        with self.assertRaises(peru.error.PrintableError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"})

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

    def test_alternate_plugins_cache(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}

            imports:
                foo: subdir
            """)
        plugins_cache = shared.create_dir()
        env_vars = {"PERU_PLUGINS_CACHE": plugins_cache}
        self.do_integration_test(["sync"], {"subdir/foo": "bar"},
                                 env_vars=env_vars)
        self.assertTrue(os.path.exists(os.path.join(plugins_cache, "cp")))
        self.assertFalse(os.path.exists(
            os.path.join(self.peru_dir, "plugins")))

    def test_override(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}
                build: mkdir subdir && mv foo subdir/builtfoo
                export: subdir

            # Test that this rule gets run in the right place (e.g. in the
            # export dir) even when the foo module is overridden.
            rule bang:
                build: printf '!' >> builtfoo

            imports:
                foo:bang: ./
            """)
        override_dir = shared.create_dir({"foo": "override"})
        # Set the override.
        run_peru_command(["override", "add", "foo", override_dir],
                         self.test_dir, self.peru_dir)
        # Confirm that the override is configured.
        output = run_peru_command(["override"], self.test_dir, self.peru_dir,
                                  capture_stdout=True)
        self.assertEqual(output, "foo: {}\n".format(override_dir))
        # Run the sync and confirm that the override worked.
        self.do_integration_test(["sync"], {"builtfoo": "override!"})
        # Delete the override.
        run_peru_command(["override", "delete", "foo"], self.test_dir,
                         self.peru_dir)
        # Confirm that the override was deleted.
        overrides = peru.override.get_overrides(self.peru_dir)
        self.assertDictEqual({}, overrides)
        # Rerun the sync and confirm the original content is back.
        self.do_integration_test(["sync"], {"builtfoo": "bar!"})

    def test_export(self):
        self.write_peru_yaml("""\
            cp module foo:
                path: {}
            """)
        # Do a simple export and check the results.
        self.do_integration_test(["export", "foo", "."], {"foo": "bar"})
        # Running the same export again should fail, because of conflicts.
        with self.assertRaises(peru.cache.Cache.DirtyWorkingCopyError):
            self.do_integration_test(["export", "foo", "."], {"foo": "bar"})
        # Passing the --force flag should pave over conflicts.
        self.do_integration_test(["export", "--force", "foo", "."],
                                 {"foo": "bar"})

    def test_help(self):
        help_output = run_peru_command(["--help"], self.test_dir,
                                       self.peru_dir, capture_stdout=True)
        self.assertEqual(peru.main.__doc__, help_output)
        # "peru" with no arguments should also print help
        no_arg_output = run_peru_command([], self.test_dir, self.peru_dir,
                                         capture_stdout=True)
        self.assertEqual(peru.main.__doc__, no_arg_output)

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

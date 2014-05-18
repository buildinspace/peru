import os
import subprocess
import textwrap
import unittest

import peru.test.shared as shared

peru_bin = os.path.join(os.path.dirname(__file__), "..", "..", "peru.sh")


class IntegrationTest(unittest.TestCase):

    def setUp(self):
        self.module_dir = shared.create_dir({
            "foo": "bar",
        })
        self.cache_dir = shared.create_dir()
        self.peru_dir = shared.create_dir()

    def tearDown(self):
        # Make sure that everything in the cache tmp dir has been cleaned up.
        tmpfiles = os.listdir(os.path.join(self.cache_dir, "tmp"))
        self.assertListEqual([], tmpfiles, msg="tmp dir is not clean")

    def write_peru_yaml(self, template):
        self.peru_yaml = textwrap.dedent(template.format(self.module_dir))
        with open(os.path.join(self.peru_dir, "peru.yaml"), "w") as f:
            f.write(self.peru_yaml)

    def do_integration_test(self, args, expected, *, silent=False,
                            env_vars=None):
        # Keep the cache dir from cluttering the expected outputs.
        env = os.environ.copy()
        env.update(env_vars or {})
        env["PERU_CACHE"] = self.cache_dir

        output = subprocess.DEVNULL if silent else None
        subprocess.check_call([peru_bin] + args, cwd=self.peru_dir, env=env,
                              stdout=output, stderr=output)

        expected_with_yaml = expected.copy()
        expected_with_yaml["peru.yaml"] = self.peru_yaml
        self.assertDictEqual(expected_with_yaml,
                             shared.read_dir(self.peru_dir))

    def test_basic_import(self):
        self.write_peru_yaml("""\
            path module foo:
                path: {}

            imports:
                foo: subdir
            """)
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})
        self.assertTrue(
            os.path.exists(os.path.join(self.cache_dir, "plugins", "path")),
            msg="Plugin cache should be written to the right place.")

        # Running it again should be a no-op.
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})

        # Running it with a dirty working copy should be an error.
        with open(os.path.join(self.peru_dir, "subdir", "foo"), "w") as f:
            f.write("dirty")
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"},
                                     silent=True)

    def test_module_rules(self):
        template = """\
            path module foo:
                path: {}
                rule:
                    build: echo -n 2 >> foo; mkdir baz; mv foo baz
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
            path module foo:
                path: {}

            imports:
                foo: subdir

            rule:
                build: echo -n hi >> lo

            rule local_build:
                build: echo -n fee >> fi
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
            path module foo:
                path: {}

            imports:
                foo: subdir
            """)
        plugins_cache = shared.create_dir()
        env_vars = {"PERU_PLUGINS_CACHE": plugins_cache}
        self.do_integration_test(["sync"], {"subdir/foo": "bar"},
                                 env_vars=env_vars)
        self.assertTrue(os.path.exists(os.path.join(plugins_cache, "path")))
        self.assertFalse(os.path.exists(
            os.path.join(self.cache_dir, "plugins")))

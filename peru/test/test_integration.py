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

    def write_peru_yaml(self, template):
        self.peru_yaml = textwrap.dedent(template.format(self.module_dir))
        with open(os.path.join(self.peru_dir, "peru.yaml"), "w") as f:
            f.write(self.peru_yaml)

    def do_integration_test(self, args, expected, *, capture_stderr=False):
        # Keep the cache dir from cluttering the expected outputs.
        env = os.environ.copy()
        env["PERU_CACHE"] = self.cache_dir

        stderr = subprocess.STDOUT if capture_stderr else None
        subprocess.check_output([peru_bin] + args, cwd=self.peru_dir, env=env,
                                stderr=stderr)

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
        # Running it again should be a no-op.
        self.do_integration_test(["sync"], {"subdir/foo": "bar"})
        # Running it with a dirty working copy should be an error.
        with open(os.path.join(self.peru_dir, "subdir", "foo"), "w") as f:
            f.write("dirty")
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_integration_test(["sync"], {"subdir/foo": "bar"},
                                     capture_stderr=True)

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

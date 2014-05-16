import os
import subprocess
from textwrap import dedent
import unittest

import peru.test.shared as shared

peru_bin = os.path.join(os.path.dirname(__file__), "..", "..", "peru.sh")


class IntegrationTest(unittest.TestCase):

    def do_integration_test(self, yaml_template, args, expected):
        module_dir = shared.create_dir({
            "foo": "bar",
        })
        peru_yaml = yaml_template.format(module_dir)
        peru_dir = shared.create_dir({
            "peru.yaml": peru_yaml,
        })
        # Keep the cache dir from cluttering the expected outputs.
        env = os.environ.copy()
        env["PERU_CACHE"] = shared.create_dir()

        subprocess.check_output([peru_bin] + args, cwd=peru_dir, env=env)

        expected_with_yaml = expected.copy()
        expected_with_yaml["peru.yaml"] = peru_yaml
        self.assertDictEqual(expected_with_yaml, shared.read_dir(peru_dir))

    def test_basic_import(self):
        yaml = dedent("""\
            path module foo:
                path: {}

            imports:
                foo: subdir
            """)
        self.do_integration_test(yaml, ["sync"], {"subdir/foo": "bar"})

    def test_build_and_export(self):
        yaml = dedent("""\
            path module foo:
                path: {}
                rule copy:
                    build: mkdir baz && cp foo baz/bing
                    export: baz

            imports:
                foo.copy: subdir
            """)
        self.do_integration_test(yaml, ["sync"], {"subdir/bing": "bar"})

    def test_local_build(self):
        yaml = dedent("""\
            path module foo:
                path: {}

            imports:
                foo: subdir

            rule local_build:
                build: cat subdir/foo > out
            """)
        self.do_integration_test(yaml, ["build", "local_build"], {
            "subdir/foo": "bar",
            "out": "bar",
        })

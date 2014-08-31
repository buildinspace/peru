from textwrap import dedent
import unittest

import shared
from shared import run_peru_command, assert_contents


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

    def do_integration_test(self, args, expected_yaml, **kwargs):
        run_peru_command(args, self.test_dir, **kwargs)
        assert_contents(self.test_dir, {'peru.yaml': expected_yaml},
                        excludes=['.peru'])

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
        self.do_integration_test(["reup", "--quiet"], expected)

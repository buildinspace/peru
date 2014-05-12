import os
import subprocess
import unittest

from peru.plugin import plugin_fetch
import peru.test.shared as shared


class PluginsTest(unittest.TestCase):

    def setUp(self):
        self.content = {"some": "stuff", "foo/bar": "baz"}
        self.content_dir = shared.create_dir(self.content)

    def do_plugin_test(self, type, plugin_fields, expected_content):
        cache_root = shared.create_dir()
        fetch_dir = shared.create_dir()
        plugin_fetch(cache_root, type, fetch_dir, plugin_fields)
        self.assertDictEqual(shared.read_dir(fetch_dir), expected_content)

    def test_git_plugin(self):
        GitRepo(self.content_dir)
        self.do_plugin_test("git", {"url": self.content_dir}, self.content)

    def test_git_plugin_with_submodule(self):
        content_repo = GitRepo(self.content_dir)
        submodule_dir = shared.create_dir({"another": "file"})
        GitRepo(submodule_dir)
        content_repo.run("git submodule add -q '{}' subdir/".format(
            submodule_dir))
        content_repo.run("git commit -q -m 'submodule commit'")
        expected_content = self.content.copy()
        expected_content["subdir/another"] = "file"
        with open(os.path.join(self.content_dir, ".gitmodules")) as f:
            expected_content[".gitmodules"] = f.read()
        self.do_plugin_test("git", {"url": self.content_dir}, expected_content)

    def test_path_plugin(self):
        self.do_plugin_test("path", {"path": self.content_dir}, self.content)


class GitRepo:
    def __init__(self, content_dir):
        self.path = content_dir
        self.run("git init -q")
        self.run("git config user.name peru")
        self.run("git config user.email peru")
        self.run("git add -A")
        self.run("git commit -q -m 'first commit'")

    def run(self, command):
        subprocess.check_call(command, shell=True, cwd=self.path)

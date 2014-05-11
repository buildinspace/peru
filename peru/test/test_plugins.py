import subprocess
import unittest

from peru.plugin import plugin_fetch
import peru.test.shared as shared


class PluginsTest(unittest.TestCase):

    def test_git(self):
        content = {"some": "stuff", "to/check": "in"}
        git_repo = GitRepo(content)
        cache_root = shared.create_dir()
        fetch_dir = shared.create_dir()
        plugin_fields = {"url": git_repo.path}
        plugin_fetch(cache_root, "git", fetch_dir, plugin_fields)
        self.assertDictEqual(shared.read_dir(fetch_dir), content)


class GitRepo:
    def __init__(self, content):
        self.path = shared.create_dir(content)
        self.run("git init -q")
        self.run("git config user.name peru")
        self.run("git config user.email peru")
        self.run("git add -A")
        self.run("git commit -q -m 'first commit'")

    def run(self, command):
        subprocess.check_call(command, shell=True, cwd=self.path)

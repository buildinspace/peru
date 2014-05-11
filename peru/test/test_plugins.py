import subprocess
import unittest

from peru.plugin import plugin_fetch
import peru.test.shared as shared


class PluginsTest(unittest.TestCase):

    def setUp(self):
        self.content = {"some": "stuff", "to/check": "in"}
        self.content_dir = shared.create_dir(self.content)
        self.fetch_dir = shared.create_dir()
        self.cache_root = shared.create_dir()

    def test_git_plugin(self):
        GitRepo(self.content_dir)
        plugin_fields = {"url": self.content_dir}
        plugin_fetch(self.cache_root, "git", self.fetch_dir, plugin_fields)
        self.assertDictEqual(shared.read_dir(self.fetch_dir), self.content)

    def test_path_plugin(self):
        plugin_fields = {"path": self.content_dir}
        plugin_fetch(self.cache_root, "path", self.fetch_dir, plugin_fields)
        self.assertDictEqual(shared.read_dir(self.fetch_dir), self.content)


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

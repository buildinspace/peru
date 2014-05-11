import subprocess
import unittest

from peru.plugin import plugin_fetch
from peru.test.shared import create_dir_with_contents, \
    read_contents_from_dir, tmp_dir


class PluginsTest(unittest.TestCase):

    def test_git(self):
        content = {"some": "stuff", "to/check": "in"}
        git_repo = GitRepo(content)
        cache_root = tmp_dir()
        fetch_dir = tmp_dir()
        plugin_fields = {"url": git_repo.path}
        plugin_fetch(cache_root, "git", fetch_dir, plugin_fields)
        self.assertDictEqual(read_contents_from_dir(fetch_dir), content)


class GitRepo:
    def __init__(self, content):
        self.path = create_dir_with_contents(content)
        self.run("git init -q")
        self.run("git config user.name peru")
        self.run("git config user.email peru")
        self.run("git add -A")
        self.run("git commit -q -m 'first commit'")

    def run(self, command):
        subprocess.check_call(command, shell=True, cwd=self.path)

import os
import subprocess
import unittest

from peru.plugin import plugin_fetch
import peru.test.shared as shared


class PluginsTest(unittest.TestCase):

    def setUp(self):
        self.content = {"some": "stuff", "foo/bar": "baz"}
        self.content_dir = shared.create_dir(self.content)
        self.cache_root = shared.create_dir()

    def do_plugin_test(self, type, plugin_fields, expected_content):
        fetch_dir = shared.create_dir()
        output = plugin_fetch(self.cache_root, type, fetch_dir, plugin_fields,
                              capture_output=True)
        self.assertDictEqual(shared.read_dir(fetch_dir), expected_content,
                             msg="Fetched content did not match expected.")
        return output

    def test_git_plugin(self):
        GitRepo(self.content_dir)
        self.do_plugin_test("git", {"url": self.content_dir}, self.content)

    def test_git_plugin_with_submodule(self):
        content_repo = GitRepo(self.content_dir)
        submodule_dir = shared.create_dir({"another": "file"})
        GitRepo(submodule_dir)
        content_repo.run("git submodule add '{}' subdir/".format(
            submodule_dir))
        content_repo.run("git commit -m 'submodule commit'")
        expected_content = self.content.copy()
        expected_content["subdir/another"] = "file"
        with open(os.path.join(self.content_dir, ".gitmodules")) as f:
            expected_content[".gitmodules"] = f.read()
        self.do_plugin_test("git", {"url": self.content_dir}, expected_content)

    def test_git_plugin_multiple_fetches(self):
        content_repo = GitRepo(self.content_dir)
        head = content_repo.run("git rev-parse HEAD").strip()
        plugin_fields = {"url": self.content_dir, "rev": head}
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 1)
        self.assertEqual(output.count("git fetch"), 0)
        del plugin_fields["rev"]
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 0)
        self.assertEqual(output.count("git fetch"), 1)

    def test_path_plugin(self):
        self.do_plugin_test("path", {"path": self.content_dir}, self.content)


class GitRepo:
    def __init__(self, content_dir):
        self.path = content_dir
        self.run("git init")
        self.run("git config user.name peru")
        self.run("git config user.email peru")
        self.run("git add -A")
        self.run("git commit -m 'first commit'")

    def run(self, command):
        output = subprocess.check_output(command, shell=True, cwd=self.path,
                                         stderr=subprocess.STDOUT)
        return output.decode('utf8')

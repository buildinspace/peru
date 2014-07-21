import os
import subprocess
import unittest

from peru.plugin import plugin_fetch, plugin_get_reup_fields
import shared
from shared import GitRepo, HgRepo


class PluginsTest(unittest.TestCase):

    def setUp(self):
        self.content = {"some": "stuff", "foo/bar": "baz"}
        self.content_dir = shared.create_dir(self.content)
        self.cache_root = shared.create_dir()

    def do_plugin_test(self, type, plugin_fields, expected_content, *,
                       hide_stderr=False):
        fetch_dir = shared.create_dir()
        output = plugin_fetch(self.cache_root, type, fetch_dir,
                              plugin_fields, capture_output=True,
                              stderr_to_stdout=hide_stderr)
        self.assertDictEqual(shared.read_dir(fetch_dir), expected_content,
                             msg="Fetched content did not match expected.")
        return output

    def test_git_plugin(self):
        GitRepo(self.content_dir)
        self.do_plugin_test("git", {"url": self.content_dir}, self.content)

    def test_hg_plugin(self):
        HgRepo(self.content_dir)
        self.do_plugin_test("hg", {"url": self.content_dir}, self.content)

    def test_git_plugin_with_submodule(self):
        content_repo = GitRepo(self.content_dir)
        submodule_dir = shared.create_dir({"another": "file"})
        GitRepo(submodule_dir)
        content_repo.run("git submodule add -q '{}' subdir/".format(
            submodule_dir))
        content_repo.run("git commit -m 'submodule commit'")
        expected_content = self.content.copy()
        expected_content["subdir/another"] = "file"
        with open(os.path.join(self.content_dir, ".gitmodules")) as f:
            expected_content[".gitmodules"] = f.read()
        self.do_plugin_test("git", {"url": self.content_dir}, expected_content)

    def test_git_plugin_multiple_fetches(self):
        content_repo = GitRepo(self.content_dir)
        head = content_repo.run("git rev-parse HEAD")
        plugin_fields = {"url": self.content_dir, "rev": head}
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 1)
        self.assertEqual(output.count("git fetch"), 0)
        # Add a new file to the directory and commit it.
        shared.write_files(self.content_dir, {'another': 'file'})
        content_repo.run("git add -A")
        content_repo.run("git commit -m 'committing another file'")
        # Refetch the original rev. Git should not do a git-fetch.
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 0)
        self.assertEqual(output.count("git fetch"), 0)
        # Not delete the rev field. Git should default to master and fetch.
        del plugin_fields["rev"]
        self.content["another"] = "file"
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 0)
        self.assertEqual(output.count("git fetch"), 1)

    def test_hg_plugin_multiple_fetches(self):
        content_repo = HgRepo(self.content_dir)
        head = content_repo.run("hg identify --debug -r .").split()[0]
        plugin_fields = {"url": self.content_dir, "rev": head}
        output = self.do_plugin_test("hg", plugin_fields, self.content)
        self.assertEqual(output.count("hg clone"), 1)
        self.assertEqual(output.count("hg pull"), 0)
        # Add a new file to the directory and commit it.
        shared.write_files(self.content_dir, {'another': 'file'})
        content_repo.run("hg commit -A -m 'committing another file'")
        # Refetch the original rev. Hg should not do a pull.
        output = self.do_plugin_test("hg", plugin_fields, self.content)
        self.assertEqual(output.count("hg clone"), 0)
        self.assertEqual(output.count("hg pull"), 0)
        # Not delete the rev field. Git should default to master and fetch.
        del plugin_fields["rev"]
        self.content["another"] = "file"
        output = self.do_plugin_test("hg", plugin_fields, self.content)
        self.assertEqual(output.count("hg clone"), 0)
        self.assertEqual(output.count("hg pull"), 1)

    def test_git_plugin_reup(self):
        repo = GitRepo(self.content_dir)
        master_head = repo.run("git rev-parse master")
        plugin_fields = {"url": self.content_dir}
        # By default, the git plugin should reup from master.
        expected_output = {"rev": master_head}
        output = plugin_get_reup_fields(
            self.cache_root, "git", plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Add some new commits and make sure master gets fetched properly.
        repo.run("git commit --allow-empty -m 'junk'")
        repo.run("git checkout -q -b newbranch")
        repo.run("git commit --allow-empty -m 'more junk'")
        new_master_head = repo.run("git rev-parse master")
        expected_output["rev"] = new_master_head
        output = plugin_get_reup_fields(
            self.cache_root, "git", plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Now specify the reup target explicitly.
        newbranch_head = repo.run("git rev-parse newbranch")
        plugin_fields["reup"] = "newbranch"
        expected_output["rev"] = newbranch_head
        output = plugin_get_reup_fields(
            self.cache_root, "git", plugin_fields)
        self.assertDictEqual(expected_output, output)

    def test_hg_plugin_reup(self):
        repo = HgRepo(self.content_dir)
        default_tip = repo.run("hg identify --debug -r default").split()[0]
        plugin_fields = {"url": self.content_dir}
        # By default, the hg plugin should reup from default.
        expected_output = {"rev": default_tip}
        output = plugin_get_reup_fields(
            self.cache_root, "hg", plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Add some new commits and make sure master gets fetched properly.
        shared.write_files(self.content_dir, {
            'randomfile': "hg doesn't like empty commits"})
        repo.run("hg commit -A -m 'junk'")
        shared.write_files(self.content_dir, {
            'randomfile': "hg still doesn't like empty commits"})
        repo.run("hg branch newbranch")
        repo.run("hg commit -A -m 'more junk'")
        new_default_tip = repo.run("hg identify --debug -r default").split()[0]
        expected_output["rev"] = new_default_tip
        output = plugin_get_reup_fields(
            self.cache_root, "hg", plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Now specify the reup target explicitly.
        newbranch_tip = repo.run("hg identify --debug -r tip").split()[0]
        plugin_fields["reup"] = "newbranch"
        expected_output["rev"] = newbranch_tip
        output = plugin_get_reup_fields(
            self.cache_root, "hg", plugin_fields)
        self.assertDictEqual(expected_output, output)

    def test_cp_plugin(self):
        self.do_plugin_test("cp", {"path": self.content_dir}, self.content)

    def test_cp_plugin_bad_fields(self):
        # "path" field is required.
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_plugin_test("cp", {}, self.content, hide_stderr=True)
        # Also test unrecognized field.
        bad_fields = {"path": self.content_dir, "junk": "junk"}
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_plugin_test("cp", bad_fields, self.content,
                                hide_stderr=True)

    def test_rsync_plugin(self):
        self.do_plugin_test("rsync", {"path": self.content_dir}, self.content)

    def test_rsync_plugin_bad_fields(self):
        # "path" field is required.
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_plugin_test("rsync", {}, self.content, hide_stderr=True)
        # Also test unrecognized field.
        bad_fields = {"path": self.content_dir, "junk": "junk"}
        with self.assertRaises(subprocess.CalledProcessError):
            self.do_plugin_test("rsync", bad_fields, self.content,
                                hide_stderr=True)

    def test_empty_plugin(self):
        self.do_plugin_test("empty", {}, {})

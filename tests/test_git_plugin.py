import importlib.machinery
from os.path import abspath, join, dirname

import peru
import shared

# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
git_plugin_path = abspath(
    join(
        dirname(peru.__file__), 'resources', 'plugins', 'git',
        'git_plugin.py'))
spec = importlib.util.spec_from_file_location("git_plugin", git_plugin_path)
git_plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_plugin)


# NOTE: The sync/reup functionality for the git plugin is tested in
# test_plugins.py along with the other plugin types.
class GitPluginTest(shared.PeruTest):
    def test_expand_relative_submodule_url(self):
        cases = [
            ("http://foo.com/a/b", "c", "c"),
            ("http://foo.com/a/b", "./c", "http://foo.com/a/b/./c"),
            ("http://foo.com/a/b", "../c", "http://foo.com/a/b/../c"),
            ("http://foo.com/a/b", "../../c", "http://foo.com/a/b/../../c"),
            ("http://foo.com/a/b", ".//../c", "http://foo.com/a/b/.//../c"),
        ]
        for (parent, submodule, expected) in cases:
            result = git_plugin.expand_relative_submodule_url(
                submodule, parent)
            assert expected == result, "{} != {}".format(expected, result)

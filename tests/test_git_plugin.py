import importlib.machinery
from os.path import abspath, join, dirname

import peru
import shared

git_plugin_path = abspath(
    join(
        dirname(peru.__file__), 'resources', 'plugins', 'git',
        'git_plugin.py'))
loader = importlib.machinery.SourceFileLoader("git_plugin", git_plugin_path)
git_plugin = loader.load_module()


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

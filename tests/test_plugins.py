import asyncio
from collections import defaultdict
import contextlib
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import unittest

from peru.async_helpers import run_task
import peru.plugin as plugin
import shared
from shared import SvnRepo, GitRepo, HgRepo, assert_contents


HG_MINIMUM_PYTHON_VERSION = (3, 6)


class TestDisplayHandle(io.StringIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_plugin_fetch(context, type, fields, dest):
    handle = TestDisplayHandle()
    run_task(plugin.plugin_fetch(context, type, fields, dest, handle))
    return handle.getvalue()


def test_plugin_get_reup_fields(context, type, fields):
    handle = TestDisplayHandle()
    return run_task(
        plugin.plugin_get_reup_fields(context, type, fields, handle))


class PluginsTest(shared.PeruTest):
    def setUp(self):
        self.content = {"some": "stuff", "foo/bar": "baz"}
        self.content_dir = shared.create_dir(self.content)
        self.cache_root = shared.create_dir()
        self.plugin_context = plugin.PluginContext(
            cwd='.',
            plugin_cache_root=self.cache_root,
            parallelism_semaphore=asyncio.BoundedSemaphore(
                plugin.DEFAULT_PARALLEL_FETCH_LIMIT),
            plugin_cache_locks=defaultdict(asyncio.Lock),
            tmp_root=shared.create_dir())
        plugin.debug_assert_clean_parallel_count()

    def tearDown(self):
        plugin.debug_assert_clean_parallel_count()

    def do_plugin_test(self,
                       type,
                       plugin_fields,
                       expected_content,
                       *,
                       fetch_dir=None):
        fetch_dir = fetch_dir or shared.create_dir()
        output = test_plugin_fetch(self.plugin_context, type, plugin_fields,
                                   fetch_dir)
        assert_contents(fetch_dir, expected_content)
        return output

    def test_git_plugin(self):
        GitRepo(self.content_dir)
        self.do_plugin_test("git", {"url": self.content_dir}, self.content)

    def test_git_default_branch(self):
        GitRepo(self.content_dir, init_default_branch='main')
        self.do_plugin_test("git", {"url": self.content_dir}, self.content)

    def test_empty_git_rev(self):
        empty_dir = shared.create_dir()
        GitRepo(empty_dir)
        self.do_plugin_test('git', {'url': empty_dir}, {})

    @unittest.skipIf(
        sys.version_info < HG_MINIMUM_PYTHON_VERSION,
        "Python too old for hg",
    )
    def test_hg_plugin(self):
        HgRepo(self.content_dir)
        self.do_plugin_test("hg", {"url": self.content_dir}, self.content)

    def test_svn_plugin(self):
        repo = SvnRepo(self.content_dir)
        self.do_plugin_test('svn', {'url': repo.url}, self.content)

    def test_svn_plugin_reup(self):
        repo = SvnRepo(self.content_dir)
        plugin_fields = {'url': repo.url}
        output = test_plugin_get_reup_fields(self.plugin_context, 'svn',
                                             plugin_fields)
        self.assertDictEqual({'rev': '1'}, output)

    def test_git_plugin_with_submodule(self):
        content_repo = GitRepo(self.content_dir)
        # Git has a small bug: The .gitmodules file is always created with "\n"
        # line endings, even on Windows. With core.autocrlf turned on, that
        # causes a warning when the file is added/committed, because those line
        # endings would get replaced with "\r\n" when the file was checked out.
        # We can just turn autocrlf off for this test to silence the warning.
        content_repo.run('git', 'config', 'core.autocrlf', 'false')
        submodule_dir = shared.create_dir({'another': 'file'})
        submodule_repo = GitRepo(submodule_dir)
        content_repo.run('git', 'submodule', 'add', '-q', submodule_dir,
                         'subdir/', env={"GIT_ALLOW_PROTOCOL": "file"})
        content_repo.run('git', 'commit', '-m', 'submodule commit')
        expected_content = self.content.copy()
        expected_content['subdir/another'] = 'file'
        with open(os.path.join(self.content_dir, '.gitmodules')) as f:
            expected_content['.gitmodules'] = f.read()
        self.do_plugin_test('git', {'url': self.content_dir}, expected_content)

        # Now move the submodule forward. Make sure it gets fetched again.
        shared.write_files(submodule_dir, {'more': 'stuff'})
        submodule_repo.run('git', 'add', '-A')
        submodule_repo.run('git', 'commit', '-m', 'more stuff')
        subprocess.check_output(['git', 'pull', '-q'],
                                cwd=os.path.join(self.content_dir, 'subdir'))
        content_repo.run('git', 'commit', '-am', 'submodule update')
        expected_content['subdir/more'] = 'stuff'
        self.do_plugin_test('git', {'url': self.content_dir}, expected_content)

        # Normally when you run `git submodule add ...`, git puts two things in
        # your repo: an entry in .gitmodules, and a commit object at the
        # appropriate path inside your repo. However, it's possible for those
        # two to get out of sync, especially if you use mv/rm on a directory
        # followed by `git add`, instead of the smarter `git mv`/`git rm`. We
        # need to create this condition and check that we then ignore the
        # submodule.
        shutil.rmtree(os.path.join(self.content_dir, 'subdir'))
        content_repo.run('git', 'commit', '-am', 'inconsistent delete')
        del expected_content['subdir/another']
        del expected_content['subdir/more']
        self.do_plugin_test('git', {'url': self.content_dir}, expected_content)

        # Finally, test explicitly disabling submodule fetching. Start by
        # reverting the 'inconsistent delete' commit from above.
        content_repo.run('git', 'revert', '--no-edit', 'HEAD')
        fields = {'url': self.content_dir, 'submodules': 'false'}
        self.do_plugin_test('git', fields, expected_content)

    def test_git_plugin_with_relative_submodule(self):
        content_repo = GitRepo(self.content_dir)
        # Same autocrlf workaround as above.
        content_repo.run('git', 'config', 'core.autocrlf', 'false')

        # Similar to above, but this time we use a relative path.
        submodule_dir = shared.create_dir({'another': 'file'})
        GitRepo(submodule_dir)
        submodule_basename = os.path.basename(submodule_dir)
        relative_path = "../" + submodule_basename
        content_repo.run('git', 'submodule', 'add', '-q', relative_path,
                         'subdir/', env={"GIT_ALLOW_PROTOCOL": "file"})
        content_repo.run('git', 'commit', '-m', 'submodule commit')
        expected_content = self.content.copy()
        expected_content['subdir/another'] = 'file'
        with open(os.path.join(self.content_dir, '.gitmodules')) as f:
            expected_content['.gitmodules'] = f.read()
        self.do_plugin_test('git', {'url': self.content_dir}, expected_content)

    def test_git_plugin_multiple_fetches(self):
        content_repo = GitRepo(self.content_dir)
        head = content_repo.run('git', 'rev-parse', 'HEAD')
        plugin_fields = {"url": self.content_dir, "rev": head}
        output = self.do_plugin_test("git", plugin_fields, self.content)
        self.assertEqual(output.count("git clone"), 1)
        self.assertEqual(output.count("git fetch"), 0)
        # Add a new file to the directory and commit it.
        shared.write_files(self.content_dir, {'another': 'file'})
        content_repo.run('git', 'add', '-A')
        content_repo.run('git', 'commit', '-m', 'committing another file')
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

    @unittest.skipIf(
        sys.version_info < HG_MINIMUM_PYTHON_VERSION,
        "Python too old for hg",
    )
    def test_hg_plugin_multiple_fetches(self):
        content_repo = HgRepo(self.content_dir)
        head = content_repo.run('hg', 'identify', '--debug', '-r',
                                '.').split()[0]
        plugin_fields = {'url': self.content_dir, 'rev': head}
        output = self.do_plugin_test('hg', plugin_fields, self.content)
        self.assertEqual(output.count('hg clone'), 1)
        self.assertEqual(output.count('hg pull'), 0)
        # Add a new file to the directory and commit it.
        shared.write_files(self.content_dir, {'another': 'file'})
        content_repo.run('hg', 'commit', '-A', '-m', 'committing another file')
        # Refetch the original rev. Hg should not do a pull.
        output = self.do_plugin_test('hg', plugin_fields, self.content)
        self.assertEqual(output.count('hg clone'), 0)
        self.assertEqual(output.count('hg pull'), 0)
        # Not delete the rev field. Git should default to master and fetch.
        del plugin_fields['rev']
        self.content['another'] = 'file'
        output = self.do_plugin_test('hg', plugin_fields, self.content)
        self.assertEqual(output.count('hg clone'), 0)
        self.assertEqual(output.count('hg pull'), 1)

    def test_git_plugin_reup(self):
        repo = GitRepo(self.content_dir)
        master_head = repo.run('git', 'rev-parse', 'master')
        plugin_fields = {'url': self.content_dir}
        # By default, the git plugin should reup from master.
        expected_output = {'rev': master_head}
        output = test_plugin_get_reup_fields(self.plugin_context, 'git',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Add some new commits and make sure master gets fetched properly.
        repo.run('git', 'commit', '--allow-empty', '-m', 'junk')
        repo.run('git', 'checkout', '-q', '-b', 'newbranch')
        repo.run('git', 'commit', '--allow-empty', '-m', 'more junk')
        new_master_head = repo.run('git', 'rev-parse', 'master')
        expected_output['rev'] = new_master_head
        output = test_plugin_get_reup_fields(self.plugin_context, 'git',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Now specify the reup target explicitly.
        newbranch_head = repo.run('git', 'rev-parse', 'newbranch')
        plugin_fields['reup'] = 'newbranch'
        expected_output['rev'] = newbranch_head
        output = test_plugin_get_reup_fields(self.plugin_context, 'git',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)

    @unittest.skipIf(
        sys.version_info < HG_MINIMUM_PYTHON_VERSION,
        "Python too old for hg",
    )
    def test_hg_plugin_reup(self):
        repo = HgRepo(self.content_dir)
        default_tip = repo.run('hg', 'identify', '--debug', '-r',
                               'default').split()[0]
        plugin_fields = {'url': self.content_dir}
        # By default, the hg plugin should reup from default.
        expected_output = {'rev': default_tip}
        output = test_plugin_get_reup_fields(self.plugin_context, 'hg',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Add some new commits and make sure master gets fetched properly.
        shared.write_files(self.content_dir,
                           {'randomfile': "hg doesn't like empty commits"})
        repo.run('hg', 'commit', '-A', '-m', 'junk')
        shared.write_files(
            self.content_dir,
            {'randomfile': "hg still doesn't like empty commits"})
        repo.run('hg', 'branch', 'newbranch')
        repo.run('hg', 'commit', '-A', '-m', 'more junk')
        new_default_tip = repo.run('hg', 'identify', '--debug', '-r',
                                   'default').split()[0]
        expected_output['rev'] = new_default_tip
        output = test_plugin_get_reup_fields(self.plugin_context, 'hg',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)
        # Now specify the reup target explicitly.
        newbranch_tip = repo.run('hg', 'identify', '--debug', '-r',
                                 'tip').split()[0]
        plugin_fields['reup'] = 'newbranch'
        expected_output['rev'] = newbranch_tip
        output = test_plugin_get_reup_fields(self.plugin_context, 'hg',
                                             plugin_fields)
        self.assertDictEqual(expected_output, output)

    def test_curl_plugin_fetch(self):
        curl_content = {'myfile': 'content'}
        test_dir = shared.create_dir(curl_content)
        test_url = (Path(test_dir) / 'myfile').as_uri()
        fields = {'url': test_url}
        self.do_plugin_test('curl', fields, curl_content)
        # Run the test again with an explicit hash and an explicit filename.
        digest = hashlib.sha1()
        digest.update(b'content')
        real_hash = digest.hexdigest()
        fields['sha1'] = real_hash
        fields['filename'] = 'newname'
        self.do_plugin_test('curl', fields, {'newname': 'content'})
        # Now run it with the wrong hash, and confirm that there's an error.
        fields['sha1'] = 'wrong hash'
        with self.assertRaises(plugin.PluginRuntimeError):
            self.do_plugin_test('curl', fields, {'newname': 'content'})

    def test_curl_plugin_fetch_archives(self):
        for type in 'zip', 'tar':
            fields = {
                'url': (shared.test_resources / ('with_exe.' + type)).as_uri(),
                'unpack': type,
            }
            fetch_dir = shared.create_dir()
            self.do_plugin_test(
                'curl',
                fields, {
                    'not_exe.txt': 'Not executable.\n',
                    'exe.sh': 'echo Executable.\n',
                },
                fetch_dir=fetch_dir)
            shared.assert_not_executable(
                os.path.join(fetch_dir, 'not_exe.txt'))
            shared.assert_executable(os.path.join(fetch_dir, 'exe.sh'))

    def test_curl_plugin_fetch_evil_archive(self):
        # There are several evil archives checked in under tests/resources. The
        # others are checked directly as part of test_curl_plugin.py.
        fields = {
            'url': (shared.test_resources / '.tar').as_uri(),
            'unpack': 'tar',
        }
        with self.assertRaises(plugin.PluginRuntimeError):
            self.do_plugin_test('curl', fields, {})

    def test_curl_plugin_reup(self):
        curl_content = {'myfile': 'content'}
        test_dir = shared.create_dir(curl_content)
        test_url = (Path(test_dir) / 'myfile').as_uri()
        digest = hashlib.sha1()
        digest.update(b'content')
        real_hash = digest.hexdigest()
        fields = {'url': test_url}
        output = test_plugin_get_reup_fields(self.plugin_context, 'curl',
                                             fields)
        self.assertDictEqual({'sha1': real_hash}, output)
        # Confirm that we get the same thing with a preexisting hash.
        fields['sha1'] = 'preexisting junk'
        output = test_plugin_get_reup_fields(self.plugin_context, 'curl',
                                             fields)
        self.assertDictEqual({'sha1': real_hash}, output)

    def test_cp_plugin(self):
        self.do_plugin_test("cp", {"path": self.content_dir}, self.content)

    @unittest.skipIf(os.name == 'nt', 'the rsync plugin is Unix-only')
    def test_rsync_plugin(self):
        self.do_plugin_test("rsync", {"path": self.content_dir}, self.content)

    @unittest.skipIf(os.name != 'nt', 'the bat plugin is Windows-only')
    def test_bat_plugin(self):
        self.do_plugin_test(
            "bat", {"filename": "xyz", "message": "hello Windows"},
            {"xyz": "hello Windows\n"})

    def test_empty_plugin(self):
        self.do_plugin_test("empty", {}, {})

    def test_missing_required_field(self):
        # The 'url' field is required for git.
        try:
            self.do_plugin_test('git', {}, self.content)
        except plugin.PluginModuleFieldError as e:
            assert 'url' in e.message, 'message should mention missing field'
        else:
            assert False, 'should throw PluginModuleFieldError'

    def test_unknown_field(self):
        # The 'junk' field isn't valid for git.
        bad_fields = {'url': self.content_dir, 'junk': 'junk'}
        try:
            self.do_plugin_test('git', bad_fields, self.content)
        except plugin.PluginModuleFieldError as e:
            assert 'junk' in e.message, 'message should mention bad field'
        else:
            assert False, 'should throw PluginModuleFieldError'

    def test_user_defined_plugin(self):
        plugin_prefix = 'peru/plugins/footype/'
        fetch_file = plugin_prefix + 'fetch.py'
        reup_file = plugin_prefix + 'reup.py'
        plugin_yaml_file = plugin_prefix + 'plugin.yaml'
        fake_config_dir = shared.create_dir({
            fetch_file:
            '#! /usr/bin/env python3\nprint("hey there!")\n',
            reup_file:
            textwrap.dedent('''\
                #! /usr/bin/env python3
                import os
                outfile = os.environ['PERU_REUP_OUTPUT']
                print("name: val", file=open(outfile, 'w'))
                '''),
            plugin_yaml_file:
            textwrap.dedent('''\
                sync exe: fetch.py
                reup exe: reup.py
                required fields: []
                ''')
        })
        os.chmod(os.path.join(fake_config_dir, fetch_file), 0o755)
        os.chmod(os.path.join(fake_config_dir, reup_file), 0o755)
        fetch_dir = shared.create_dir()

        # We need to trick peru into loading plugins from the fake config dir
        # dir. We do this by setting an env var, which depends on the platform.
        if os.name == 'nt':
            # Windows
            config_path_variable = 'LOCALAPPDATA'
        else:
            # non-Windows
            config_path_variable = 'XDG_CONFIG_HOME'

        with temporary_environment(config_path_variable, fake_config_dir):
            output = test_plugin_fetch(self.plugin_context, 'footype', {},
                                       fetch_dir)
            self.assertEqual('hey there!\n', output)
            output = test_plugin_get_reup_fields(self.plugin_context,
                                                 'footype', {})
            self.assertDictEqual({'name': 'val'}, output)

    def test_no_such_plugin(self):
        with self.assertRaises(plugin.PluginCandidateError):
            test_plugin_fetch(self.plugin_context, 'nosuchtype!', {},
                              os.devnull)


@contextlib.contextmanager
def temporary_environment(name, value):
    NOT_SET = object()
    old_value = os.environ.get(name, NOT_SET)
    os.environ[name] = value
    try:
        yield
    finally:
        if old_value is NOT_SET:
            del os.environ[name]
        else:
            os.environ[name] = old_value

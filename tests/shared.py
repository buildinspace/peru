import difflib
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap

from peru.compat import makedirs
import peru.main


test_resources = Path(__file__).parent.resolve() / 'resources'


def tmp_dir():
    return tempfile.mkdtemp(dir=_tmp_root())


def tmp_file():
    fd, name = tempfile.mkstemp(dir=_tmp_root())
    os.close(fd)
    return name


def _tmp_root():
    root = os.path.join(tempfile.gettempdir(), 'peru', 'test')
    makedirs(root)
    return root


def create_dir(path_contents_map=None):
    dir = tmp_dir()
    if path_contents_map:
        write_files(dir, path_contents_map)
    return dir


def write_files(dir, path_contents_map):
    dir = Path(dir)
    for path, contents in path_contents_map.items():
        path = Path(path)
        full_path = dir / path
        makedirs(str(full_path.parent))
        with full_path.open('w') as f:
            f.write(contents)


def read_dir(startdir, excludes=()):
    assert isinstance(excludes, list) or isinstance(excludes, tuple), \
        "excludes must be a list or a tuple, not " + repr(type(excludes))
    startdir = Path(startdir)
    exclude_tuples = [Path(e).parts for e in excludes]
    contents = {}
    for p in startdir.glob('**/*'):
        if not p.is_file():
            continue
        relpath = p.relative_to(startdir)
        if any(relpath.parts[:len(tup)] == tup for tup in exclude_tuples):
            continue
        # Open in binary mode to avoid newline conversions.
        with p.open('rb') as f:
            try:
                contents[relpath] = f.read().decode()
            except UnicodeDecodeError:
                contents[relpath] = '<BINARY>'
    return contents


def _format_contents(contents):
    return ['{}: {}\n'.format(file, repr(contents[file]))
            for file in sorted(contents.keys())]


def assert_contents(dir, expected_contents, *, message='', excludes=()):
    dir = Path(dir)
    expected_contents = {Path(key): val for key, val
                         in expected_contents.items()}
    actual_contents = read_dir(dir, excludes)
    if expected_contents == actual_contents:
        return
    # Make sure we didn't exclude files we were checking for.
    full_contents = read_dir(dir)
    excluded_files = full_contents.keys() - actual_contents.keys()
    excluded_missing = expected_contents.keys() & excluded_files
    if excluded_missing:
        raise AssertionError('EXPECTED FILES WERE EXCLUDED FROM THE TEST: {}'
                             .format(excluded_missing))
    # Make a diff against expected and throw.
    assertion_msg = "Contents didn't match:\n" + ''.join(
        difflib.unified_diff(_format_contents(expected_contents),
                             _format_contents(actual_contents),
                             fromfile='expected', tofile='actual')).strip()
    if message:
        assertion_msg += '\n' + message
    raise AssertionError(assertion_msg)


def assert_tree_contents(cache, tree, expected_contents, **kwargs):
    export_dir = create_dir()
    cache.export_tree(tree, export_dir)
    assert_contents(export_dir, expected_contents, **kwargs)


def assert_clean_tmp(peru_dir):
    tmp_root = os.path.join(peru_dir, 'tmp')
    if os.path.exists(tmp_root):
        tmpfiles = os.listdir(tmp_root)
        assert not tmpfiles, 'main tmp dir is not clean: ' + str(tmpfiles)
    cache_tmp_root = os.path.join(peru_dir, 'cache', 'tmp')
    if os.path.exists(cache_tmp_root):
        tmpfiles = os.listdir(cache_tmp_root)
        assert not tmpfiles, 'cache tmp dir is not clean: ' + str(tmpfiles)


def run_peru_command(args, cwd, *, env=None):
    old_cwd = os.getcwd()
    old_stdout = sys.stdout
    os.chdir(cwd)
    capture_stream = io.StringIO()
    sys.stdout = capture_stream
    try:
        # Rather than invoking peru as a subprocess, just call directly into
        # the Main class. This lets us check that the right types of exceptions
        # make it up to the top, so we don't need to check specific output
        # strings.
        peru.main.main(argv=args, env=env or {}, nocatch=True)
    finally:
        os.chdir(old_cwd)
        sys.stdout = old_stdout
    return capture_stream.getvalue()


class Repo:
    def __init__(self, path):
        self.path = path

    def run(self, *command):
        output = subprocess.check_output(command, cwd=self.path)
        return output.decode('utf8').strip()


class GitRepo(Repo):
    def __init__(self, content_dir):
        super().__init__(content_dir)

        self.run('git', 'init')
        self.run('git', 'config', 'user.name', 'peru')
        self.run('git', 'config', 'user.email', 'peru')
        self.run('git', 'add', '-A')
        self.run('git', 'commit', '--allow-empty', '-m', 'first commit')


class HgRepo(Repo):
    def __init__(self, content_dir):
        super().__init__(content_dir)

        self.run('hg', 'init')
        hgrc_path = os.path.join(content_dir, '.hg', 'hgrc')
        with open(hgrc_path, 'a') as f:
            f.write(textwrap.dedent('''\
                [ui]
                username = peru <peru>
                '''))
        self.run('hg', 'commit', '-A', '-m', 'first commit')


class SvnRepo(Repo):
    def __init__(self, content_dir):
        # SVN can't create a repo "in place" like git or hg.
        repo_dir = create_dir()
        super().__init__(repo_dir)
        self.url = Path(repo_dir).as_uri()

        self.run('svnadmin', 'create', '.')
        self.run('svn', 'import', content_dir, self.url,
                 '-m', 'initial commit')


def _check_executable(path, expectation):
    if os.name == 'nt':
        # Windows doesn't support the executable flag. Skip the check.
        return
    mode = Path(path).stat().st_mode
    is_executable = (mode & stat.S_IXUSR != 0 and
                     mode & stat.S_IXGRP != 0 and
                     mode & stat.S_IXOTH != 0)
    message = 'Expected {} to be {}executable.'.format(
        path, 'not ' if not expectation else '')
    assert is_executable == expectation, message


def assert_executable(path):
    _check_executable(path, True)


def assert_not_executable(path):
    _check_executable(path, False)

import difflib
import io
import os
import subprocess
import sys
import tempfile
import textwrap

from peru.compat import makedirs
import peru.main


def tmp_dir():
    return tempfile.mkdtemp(dir=_tmp_root())


def tmp_file():
    fd, name = tempfile.mkstemp(dir=_tmp_root())
    os.close(fd)
    return name


def _tmp_root():
    root = '/tmp/peru/test'
    makedirs(root)
    return root


def create_dir(path_contents_map=None):
    dir = tmp_dir()
    if path_contents_map:
        write_files(dir, path_contents_map)
    return dir


def write_files(dir, path_contents_map):
    for path, contents in path_contents_map.items():
        full_path = os.path.join(dir, path)
        full_parent = os.path.dirname(full_path)
        if not os.path.isdir(full_parent):
            os.makedirs(full_parent)
        with open(full_path, "w") as f:
            f.write(contents)


def read_dir(startdir, excludes=()):
    contents = {}
    for subpath, dirs, files in os.walk(startdir):
        # Read the contents of files, excepting excludes.
        for file in files:
            filepath = os.path.join(subpath, file)
            relpath = os.path.relpath(filepath, startdir)
            if relpath in excludes:
                continue
            with open(filepath) as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    content = '<BINARY>'
            contents[relpath] = content
        # Avoid recursing into excluded subdirectories.
        for dir in dirs.copy():  # copy, because we're going to modify it
            dirpath = os.path.join(subpath, dir)
            relpath = os.path.relpath(dirpath, startdir)
            if relpath in excludes:
                dirs.remove(dir)
    return contents


def _format_contents(contents):
    return ['{}: {}\n'.format(file, repr(contents[file]))
            for file in sorted(contents.keys())]


def assert_contents(dir, expected_contents, excludes=()):
    # Ignore peru.yaml and .peru by default.
    actual_contents = read_dir(dir, excludes)
    if expected_contents == actual_contents:
        return
    # Make sure we didn't exclude files we were checking for.
    full_contents = read_dir(dir)
    excluded_files = full_contents.keys() - actual_contents.keys()
    excluded_missing = expected_contents.keys() & excluded_files
    if excluded_missing:
        raise AssertionError('EXPECTED FILES WERE EXCLUDED FROM THE TEST: ' +
                             ', '.join(excluded_missing))
    # Make a diff against expected and throw.
    raise AssertionError("Contents didn't match:\n" + ''.join(
        difflib.unified_diff(_format_contents(expected_contents),
                             _format_contents(actual_contents),
                             fromfile='expected', tofile='actual')).strip())


def run_peru_command(args, test_dir, *, env_vars=None):
    old_cwd = os.getcwd()
    old_stdout = sys.stdout
    os.chdir(test_dir)
    capture_stream = io.StringIO()
    sys.stdout = capture_stream
    try:
        # Rather than invoking peru as a subprocess, just call directly into
        # the Main class. This lets us check that the right types of exceptions
        # make it up to the top, so we don't need to check specific outputs
        # strings.
        peru.main.Main().run(args, env_vars or {})
    finally:
        os.chdir(old_cwd)
        sys.stdout = old_stdout
    return capture_stream.getvalue()


class Repo:
    def __init__(self, path):
        self.path = path

    def run(self, command):
        output = subprocess.check_output(command, shell=True, cwd=self.path)
        return output.decode('utf8').strip()


class GitRepo(Repo):
    def __init__(self, content_dir):
        super().__init__(content_dir)

        self.run("git init")
        self.run("git config user.name peru")
        self.run("git config user.email peru")
        self.run("git add -A")
        self.run("git commit --allow-empty -m 'first commit'")


class HgRepo(Repo):
    def __init__(self, content_dir):
        super().__init__(content_dir)

        self.run("hg init")
        hgrc_path = os.path.join(content_dir, ".hg", "hgrc")
        with open(hgrc_path, "a") as f:
            f.write(textwrap.dedent("""\
                [ui]
                username = peru <peru>
                """))
        self.run("hg commit -A -m 'first commit'")


class SvnRepo(Repo):
    def __init__(self, content_dir):
        # SVN can't create a repo "in place" like git or hg.
        repo_dir = create_dir()
        super().__init__(repo_dir)
        self.url = 'file://' + repo_dir

        self.run('svnadmin create .')
        self.run('svn import {} {} -m "initial commit"'.format(
            content_dir, self.url))

import os
import subprocess
import tempfile
import textwrap

from peru.compat import makedirs


def tmp_dir():
    return tempfile.mkdtemp(dir=_tmp_root())


def tmp_file():
    fd, name = tempfile.mkstemp(dir=_tmp_root())
    os.close(fd)
    return name


def _tmp_root():
    root = "/tmp/perutest"
    makedirs(root)
    os.chmod(root, 0o777)
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


def read_dir(dir):
    contents = {}
    for subdir, _, files in os.walk(dir):
        for file in files:
            path = os.path.normpath(os.path.join(subdir, file))
            with open(path) as f:
                content = f.read()
            relpath = os.path.relpath(path, dir)
            contents[relpath] = content
    return contents


class Repo:
    def __init__(self, path=None):
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

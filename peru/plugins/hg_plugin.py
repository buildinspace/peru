#! /usr/bin/env python3

import os
import os.path as path
import shutil
import subprocess
import textwrap
import urllib.parse

from peru.plugin_shared import plugin_main


def hg(*args, hg_dir=None):
    # avoid forgetting this arg
    assert hg_dir is None or path.isdir(hg_dir)
    command = ["hg"]
    if hg_dir:
        command.append("--repository")
        command.append(hg_dir)
    command.extend(args)
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            "Command exited with error code {0}:\n$ {1}\n{2}"
            .format(process.returncode, " ".join(command), output))
    return output


def repo_cache_path(url, cache_root):
    escaped = urllib.parse.quote(url, safe="")
    return path.join(cache_root, escaped)


def hg_clone_if_needed(url, cache_path):
    repo_path = repo_cache_path(url, cache_path)
    if not path.exists(repo_path):
        os.makedirs(repo_path)
        try:
            print("hg clone", url)
            hg("clone", "--noupdate", url, repo_path)
        except:
            # Delete the whole thing if the clone failed, to avoid
            # confusing the cache.
            shutil.rmtree(repo_path)
            raise
        hg_configure(repo_path)
    return repo_path


def hg_configure(repo_path):
    """Set configs we need for our cached repos."""
    hgrc_path = os.path.join(repo_path, ".hg", "hgrc")
    with open(hgrc_path, "a") as f:
        f.write(textwrap.dedent("""\
            [ui]
            # prevent "hg archive" from creating '.hg_archival.txt' files.
            archivemeta = false
            """))


def do_fetch(fields, dest, cache_path):
    url, rev, reup = parse_fields(fields)
    clone = hg_clone_if_needed(url, cache_path)
    # TODO: Handle subrepos?
    hg("archive", "--type", "files", "--rev", rev, dest, hg_dir=clone)


def parse_fields(fields):
    return (fields["url"],
            fields.get("rev", "default"),
            fields.get("reup", "default"))

required_fields = {"url"}
optional_fields = {"rev", "reup"}

if __name__ == "__main__":
    plugin_main(required_fields, optional_fields, do_fetch, None)

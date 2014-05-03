#! /usr/bin/env python3

import configparser
import os
from os import path
import shutil
import subprocess
import sys
import urllib.parse


class GitJob:
    def __init__(self, cache_path, dest, url, rev):
        self.cache_path = cache_path
        self.dest = dest
        self.url = url
        self.rev = rev
        self.run()

    def git(self, git_dir, *args):
        if set(args) & {"clone", "fetch", "checkout"}:
            logline = "git " + " ".join(args)
            if len(logline) > 80:
                logline = logline[:77] + "..."
            print(logline)
        # avoid forgetting this arg
        assert git_dir is None or path.isdir(git_dir)
        command = ["git"]
        if git_dir:
            command.append("--git-dir=" + git_dir)
        command.extend(args)
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True)
        output, _ = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                "Command exited with error code {0}:\n$ {1}\n{2}"
                .format(process.returncode, " ".join(command), output))
        return output

    def git_clone_cached(self, url):
        escaped = urllib.parse.quote(url, safe="")
        repo_path = path.join(self.cache_path, escaped)
        if not path.exists(repo_path):
            os.makedirs(repo_path)
            try:
                self.git(None, "clone", "--mirror", url, repo_path)
            except:
                # Delete the whole thing if the clone failed, to avoid
                # confusing the cache.
                shutil.rmtree(repo_path)
                raise
        return repo_path

    def git_already_has_rev(self, repo, rev):
        try:
            # make sure it exists
            self.git(repo, "cat-file", "-e", rev)
            # get the hash for this rev
            output = self.git(repo, "rev-parse", rev)
        except:
            return False
        # Only return true for revs that are absolute hashes.
        # TODO: Should we assume that tags are reliable?
        return output.strip() == rev

    def checkout_tree(self, clone, rev, dest):
        self.git(clone, "--work-tree=" + dest, "checkout", rev, "--", ".")
        self.handle_subrepos(clone, rev, dest)

    def handle_subrepos(self, clone_path, rev, work_tree):
        gitmodules = os.path.join(work_tree, ".gitmodules")
        if not os.path.exists(gitmodules):
            return
        parser = configparser.ConfigParser()
        parser.read(gitmodules)
        for section in parser.sections():
            sub_relative_path = parser[section]["path"]
            sub_full_path = os.path.join(work_tree, sub_relative_path)
            sub_url = parser[section]["url"]
            sub_clone = self.git_clone_cached(sub_url)
            ls_tree = self.git(clone_path, "ls-tree", "-r", rev,
                               sub_relative_path)
            sub_rev = ls_tree.split()[2]
            self.checkout_tree(sub_clone, sub_rev, sub_full_path)

    def run(self):
        cached_dir = self.git_clone_cached(self.url)
        if not self.git_already_has_rev(cached_dir, self.rev):
            self.git(cached_dir, "fetch", "--prune")
        self.checkout_tree(cached_dir, self.rev, self.dest)


def main():
    sys.argv.pop(0)  # exe name
    assert sys.argv.pop(0) == "--cache"
    cache_path = sys.argv.pop(0)
    assert sys.argv.pop(0) == "fetch"
    dest = sys.argv.pop(0)

    url = None
    rev = "master"

    while sys.argv:
        name = sys.argv.pop(0)
        val = sys.argv.pop(0)
        if name == "--url":
            url = val
        elif name == "--rev":
            rev = val
        else:
            raise RuntimeError("Unknown plugin field name: " + name)

    assert url is not None

    GitJob(cache_path, dest, url, rev)

if __name__ == "__main__":
    main()

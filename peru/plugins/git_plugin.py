import os
from os import path
import shutil
import subprocess
import sys
import urllib.parse

class GitJob:
    def __init__(self, runtime, name, fields, target):
        self.runtime = runtime
        self.name = name
        self.fields = fields
        self.target = target
        self.run()

    def git(self, git_dir, *args):
        if self.runtime.verbose and set(args) & {"clone", "fetch", "checkout"}:
            logline = "git " + " ".join(args)
            if len(logline) > 80:
                logline = logline[:77] + "..."
            print(logline)
        assert git_dir is None or path.isdir(git_dir) # avoid forgetting this arg
        command = ["git"]
        if git_dir:
            command.append("--git-dir=" + git_dir)
        command.extend(args)
        process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, universal_newlines=True)
        output, _ = process.communicate()
        if process.returncode != 0:
            raise RuntimeError("Command exited with error code {0}:\n$ {1}\n{2}"
                            .format(process.returncode, " ".join(command),
                                    output))
        return output

    def git_clone_cached(self, url):
        escaped = urllib.parse.quote(url, safe="")
        repo_path = path.join(self.runtime.cache.root, "git", escaped)
        if not path.exists(repo_path):
            os.makedirs(repo_path)
            try:
                self.git(None, "clone", "--mirror", url, repo_path)
            except:
                # Delete the whole thing if the clone failed, to avoid confusing
                # the cache.
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

    def run(self):
        url = self.fields["url"]
        rev = self.fields.get("rev", "master")
        cached_dir = self.git_clone_cached(url)
        if not self.git_already_has_rev(cached_dir, rev):
            self.git(cached_dir, "fetch", "--prune")
        # Checkout the specified revision from the clone into the target dir.
        self.git(cached_dir, "--work-tree=" + self.target,
                 "checkout", rev, "--", ".")

def peru_plugin_main(*args, **kwargs):
    runtime = kwargs["runtime"]
    def callback(fields, target, name):
        GitJob(runtime, name, fields, target)
    kwargs["register"](
        name="git",
        required_fields={"url"},
        optional_fields = {"rev"},
        get_files_callback = callback,
    )

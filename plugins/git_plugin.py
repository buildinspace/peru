import os
from os import path
import shutil
import subprocess
import urllib.parse

def git(git_dir, *args):
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

def git_clone_cached(runtime, url, name):
    escaped = urllib.parse.quote(url, safe="")
    repo_path = path.join(runtime.cache.root, "git", escaped)
    if not path.exists(repo_path):
        runtime.log("cloning {}...".format(name))
        os.makedirs(repo_path)
        try:
            git(None, "clone", "--mirror", url, repo_path)
        except:
            # Delete the whole thing if the clone failed, to avoid confusing
            # the cache.
            shutil.rmtree(repo_path)
            raise
    return repo_path

def git_already_has_rev(repo, rev):
    try:
        # make sure it exists
        git(repo, "cat-file", "-e", rev)
        # get the hash for this rev
        output = git(repo, "rev-parse", rev)
    except:
        return False
    # Only return true for revs that are absolute hashes.
    # TODO: Should we assume that tags are reliable?
    return output.strip() == rev

def get_files_callback(runtime, fields, target, name):
    url = fields["url"]
    rev = fields.get("rev", "master")
    cached_dir = git_clone_cached(runtime, url, name)
    if not git_already_has_rev(cached_dir, rev):
        runtime.log("fetching {}...".format(name))
        git(cached_dir, "fetch", "--prune")
    # Checkout the specified revision from the clone into the target dir.
    git(cached_dir, "--work-tree=" + target, "checkout", rev, "--", ".")

def peru_plugin_main(*args, **kwargs):
    runtime = kwargs["runtime"]
    def callback_wrapper(fields, target, name):
        return get_files_callback(runtime, fields, target, name)
    kwargs["register"](
        name="git",
        required_fields={"url"},
        optional_fields = {"rev"},
        get_files_callback = callback_wrapper,
    )

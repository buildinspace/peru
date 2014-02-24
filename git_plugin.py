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
    return subprocess.check_output(
        command, stderr=subprocess.STDOUT, universal_newlines=True)


def git_clone_cached(url):
    escaped = urllib.parse.quote(url, safe="")
    # Use $PERU_CACHE_NAME if defined, otherwise use the default root path.
    root_path = os.getenv("PERU_CACHE_NAME") or ".peru-cache"
    cached_path = path.join(root_path, "git", escaped)
    if not path.exists(cached_path):
        print("cloning...")
        os.makedirs(cached_path)
        try:
            git(None, "clone", "--mirror", url, cached_path)
        except:
            # Delete the whole thing if the clone failed, to avoid confusing
            # the cache.
            shutil.rmtree(cached_path)
            raise
    return cached_path


def get_files_callback(fields, target):
    url = fields["url"]
    rev = fields["rev"]
    cached_dir = git_clone_cached(url)
    # TODO: Eventually avoid this fetch by caching outputs.
    print("fetching...")
    git(cached_dir, "fetch", "--prune")
    # Checkout the specified revision from the clone into the target dir.
    git(cached_dir, "--work-tree=" + target, "checkout", rev, "--", ".")


peru_register(
    name="git_module",
    fields=("url", "rev"),
    get_files_callback = get_files_callback,
)

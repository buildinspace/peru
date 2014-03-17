import os
from os import path
import shutil
import subprocess
import urllib.parse


peru_cache_root = None
is_verbose = False


def verbose(*args, **kwargs):
    if is_verbose:
        print(*args, **kwargs)


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


def git_clone_cached(url):
    escaped = urllib.parse.quote(url, safe="")
    repo_path = path.join(peru_cache_root(), "git", escaped)
    if not path.exists(repo_path):
        verbose("cloning...")
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


def get_files_callback(fields, target):
    url = fields["url"]
    rev = fields["rev"]
    cached_dir = git_clone_cached(url)
    if not git_already_has_rev(cached_dir, rev):
        verbose("fetching...")
        git(cached_dir, "fetch", "--prune")
    # Checkout the specified revision from the clone into the target dir.
    git(cached_dir, "--work-tree=" + target, "checkout", rev, "--", ".")


def peru_plugin_main(*args, **kwargs):
    global peru_cache_root, is_verbose
    peru_cache_root = kwargs["cache_root"]
    is_verbose = kwargs["verbose"]
    kwargs["register"](
        name="git",
        required_fields={"url", "rev"},
        optional_fields = set(),
        get_files_callback = get_files_callback,
    )

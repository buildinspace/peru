#! /usr/bin/env python3

import os
import shutil
import subprocess
import urllib.parse


def git(*args, git_dir=None):
    # Avoid forgetting this arg.
    assert git_dir is None or os.path.isdir(git_dir)

    command = ['git']
    if git_dir:
        command.append('--git-dir={0}'.format(git_dir))
    command.extend(args)

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))

    return output


def has_clone(url, cache_path):
    return os.path.exists(repo_cache_path(url, cache_path))


def clone_if_needed(url, cache_path):
    repo_path = repo_cache_path(url, cache_path)
    if not has_clone(url, cache_path):
        try:
            git('clone', '--mirror', url, repo_path)
        except:
            # Delete the whole thing if the clone failed to avoid confusing the
            # cache.
            shutil.rmtree(repo_path)
            raise
    return repo_path


def repo_cache_path(url, cache_root):
    escaped = urllib.parse.quote(url, safe='')

    return os.path.join(cache_root, escaped)

#! /usr/bin/env python3

import os
import shutil
import subprocess
import urllib.parse


required_fields = {'url'}
optional_fields = {'rev', 'reup'}


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


def clone_if_needed(url, cache_path, log_fn=None):
    repo_path = repo_cache_path(url, cache_path)
    if not os.path.exists(repo_path):
        os.makedirs(repo_path)
        try:
            if log_fn:
                log_fn()
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


def unpack_fields(fields):
    return (fields['url'],
            fields.get('rev', 'master'),
            fields.get('reup', 'master'))

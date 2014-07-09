#! /usr/bin/env python3

import os
import shutil
import subprocess
import textwrap
import urllib.parse


required_fields = {'url'}
optional_fields = {'rev', 'reup'}


def hg(*args, hg_dir=None):
    # Avoid forgetting this arg.
    assert hg_dir is None or os.path.isdir(hg_dir)

    command = ['hg']
    if hg_dir:
        command.append('--repository')
        command.append(hg_dir)
    command.extend(args)

    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))

    return output


def clone_if_needed(url, cache_path, verbose=False):
    repo_path = repo_cache_path(url, cache_path)
    if not os.path.exists(repo_path):
        os.makedirs(repo_path)
        try:
            if verbose:
                print('hg clone', url)
            hg('clone', '--noupdate', url, repo_path)
        except:
            # Delete the whole thing if the clone failed to avoid confusing the
            # cache.
            shutil.rmtree(repo_path)
            raise

        configure(repo_path)

    return repo_path


def configure(repo_path):
    # Set configs needed for cached repos.
    hgrc_path = os.path.join(repo_path, '.hg', 'hgrc')
    with open(hgrc_path, 'a') as f:
        f.write(textwrap.dedent('''\
            [ui]
            # prevent 'hg archive' from creating '.hg_archival.txt' files.
            archivemeta = false
            '''))


def already_has_rev(repo, rev):
    try:
        output = hg('identify', '--debug', '--rev', rev, hg_dir=repo)
    except:
        return False

    # Only return True for revs that are absolute hashes.
    # We could consider treating tags the way, but...
    # 1) Tags actually can change.
    # 2) It's not clear at a glance whether something is a branch or a hash.
    # Keep it simple.
    return output.split()[0] == rev


def repo_cache_path(url, cache_root):
    escaped = urllib.parse.quote(url, safe='')

    return os.path.join(cache_root, escaped)


def unpack_fields(fields):
    return (fields['url'],
            fields.get('rev', 'default'),
            fields.get('reup', 'default'))

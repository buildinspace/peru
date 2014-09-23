#! /usr/bin/env python3

import os
import shutil
import subprocess
import textwrap


def hg(*args, hg_dir=None, capture_output=False):
    # Avoid forgetting this arg.
    assert hg_dir is None or os.path.isdir(hg_dir)

    command = ['hg']
    if hg_dir:
        command.append('--repository')
        command.append(hg_dir)
    command.extend(args)

    stdout = subprocess.PIPE if capture_output else None
    stderr = subprocess.STDOUT if capture_output else None
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                               stderr=stderr, universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))

    return output


def clone_if_needed(url, cache_path, verbose=False):
    if not os.path.exists(os.path.join(cache_path, '.hg')):
        try:
            if verbose:
                print('hg clone', url)
            hg('clone', '--noupdate', url, cache_path)
        except:
            # Delete the whole thing if the clone failed to avoid confusing the
            # cache.
            shutil.rmtree(cache_path)
            raise
        configure(cache_path)
    return cache_path


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
        output = hg('identify', '--debug', '--rev', rev, hg_dir=repo,
                    capture_output=True)
    except:
        return False

    # Only return True for revs that are absolute hashes.
    # We could consider treating tags the way, but...
    # 1) Tags actually can change.
    # 2) It's not clear at a glance whether something is a branch or a hash.
    # Keep it simple.
    return output.split()[0] == rev

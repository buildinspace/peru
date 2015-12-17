#! /usr/bin/env python3

import os
import os.path
import shutil
import subprocess


def bzr(path, *args, capture_output=False):
    command = ['bzr']
    command.extend(args)
    stdout = subprocess.PIPE if capture_output else None
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=stdout, cwd=path,
                               universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))
    return output


def clone_if_needed(bzr_path, url):
    if os.path.exists(os.path.join(bzr_path, '.bzr')):
        return False
    try:
        bzr(bzr_path, 'branch', '--use-existing-dir', url, '.',
            capture_output=True)
        return True
    except:
        shutil.rmtree(bzr_path)
        raise


def pull_if_needed(bzr_path, url, rev):
    try:
        bzr(bzr_path, 'revno', '-r', rev)
    except:
        bzr(bzr_path, 'pull', url)


def sync():
    cache_path = os.environ['PERU_PLUGIN_CACHE']
    dest = os.environ['PERU_SYNC_DEST']
    rev = os.environ['PERU_MODULE_REV'] or 'last:1'
    url = os.environ['PERU_MODULE_URL']

    if not clone_if_needed(cache_path, url):
        pull_if_needed(cache_path, url, rev)
    bzr(cache_path, 'export', '-r', rev, dest)


def reup():
    cache_path = os.environ['PERU_PLUGIN_CACHE']
    reup_output = os.environ['PERU_REUP_OUTPUT']
    url = os.environ['PERU_MODULE_URL']

    if not clone_if_needed(cache_path, url):
        bzr(cache_path, 'pull', url)
    output = bzr(cache_path, 'revno', capture_output=True)

    with open(reup_output, 'w') as output_file:
        print('rev: "{}"'.format(output.strip()), file=output_file)


def main():
    command = os.environ['PERU_PLUGIN_COMMAND']
    if command == 'sync':
        sync()
    elif command == 'reup':
        reup()
    else:
        raise RuntimeError('Unknown command: ' + repr(command))


if __name__ == '__main__':
    main()

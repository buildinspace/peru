#! /usr/bin/env python3

import os
import subprocess
import sys


required_fields = {'url'}
optional_fields = {'rev', 'reup'}


def svn(*args, svn_dir=None):
    # Avoid forgetting this arg.
    assert svn_dir is None or os.path.isdir(svn_dir)

    command = ['svn', '--non-interactive']
    command.extend(args)

    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, cwd=svn_dir, universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))

    return output


def remote_head_rev(url):
    info = svn('info', url).split('\n')
    for item in info:
        if item.startswith('Revision: '):
            return item.split()[1]

    print('svn revision info not found', file=sys.stderr)
    sys.exit(1)


def unpack_fields(fields):
    return (fields['url'],
            fields.get('rev', 'HEAD'),
            fields.get('reup', 'HEAD'))

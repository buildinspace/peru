#! /usr/bin/env python3

import os
import subprocess


def svn(*args, svn_dir=None, capture_output=False):
    # Avoid forgetting this arg.
    assert svn_dir is None or os.path.isdir(svn_dir)

    command = ['svn', '--non-interactive']
    command.extend(args)

    stdout = subprocess.PIPE if capture_output else None
    stderr = subprocess.STDOUT if capture_output else None
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
        cwd=svn_dir, universal_newlines=True)
    output, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            'Command exited with error code {0}:\n$ {1}\n{2}'.format(
                process.returncode,
                ' '.join(command),
                output))

    return output

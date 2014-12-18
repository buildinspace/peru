#! /usr/bin/env python3

import os
import sys
import subprocess

REPO_ROOT = os.path.dirname(os.path.realpath(__file__))
TESTS_DIR = os.path.join(REPO_ROOT, 'tests')
THIRD_PARTY_DIR = os.path.join(REPO_ROOT, 'third-party')


def get_untracked_files():
    output = subprocess.check_output(
        ['git', 'ls-files', '--other', '--directory', '--exclude-standard',
            '-z'],
        cwd=REPO_ROOT)
    return set(f for f in output.split(b'\0') if f)


def main():
    # Unset any PERU environment variables to make sure test runs don't get
    # thrown off by anything in your bashrc.
    for var in os.environ:
        if var.startswith('PERU_'):
            del os.environ[var]

    # Turn debugging features on for the asyncio library.
    os.environ['PYTHONASYNCIODEBUG'] = '1'

    # Make sure the tests don't create any garbage files in the repo. That
    # tends to happen when we accidentally run something in the current dir
    # that should be in a temp dir, and it's hard to track down when it does.
    old_untracked = get_untracked_files()

    # Run the actual tests.
    env = os.environ.copy()
    env['PYTHONPATH'] = ':'.join((REPO_ROOT, THIRD_PARTY_DIR))
    args = sys.argv[1:]
    if len(args) > 0 and args[0] == '--with-coverage':
        args.pop(0)
        command_start = ['coverage', 'run']
    else:
        command_start = [sys.executable]
    command = command_start + ['-m', 'unittest'] + args
    try:
        subprocess.check_call(command, env=env, cwd=TESTS_DIR)
    except:
        sys.exit(1)

    new_untracked = get_untracked_files()
    if old_untracked != new_untracked:
        print('Tests created untracked files:\n' +
              '\n'.join(f.decode() for f in new_untracked - old_untracked),
              file=sys.stderr)
        sys.exit(1)

    # Run the linter.
    try:
        subprocess.check_call(['flake8', 'peru', 'tests'], cwd=REPO_ROOT)
    except:
        sys.exit(1)


if __name__ == '__main__':
    main()

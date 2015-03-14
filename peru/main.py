#! /usr/bin/env python3

import asyncio
import os
import sys
import tempfile

import docopt

from . import async
from . import compat
from .error import PrintableError
from . import imports
from . import parser
from .runtime import Runtime

__doc__ = """\
Usage:
  peru sync [-fqv] [-j N]
  peru reup [-fqv] [-j N] [--nosync] [<modules>...]
  peru override [list | add <module> <path> | delete <module>]
  peru copy [-fqv] [-j N] <target> [<dest>]
  peru clean [-fv]
  peru (help | --help | --version)

Commands:
  sync      fetch imports and copy them to your project
  reup      update the version information for your modules
  override  read from a local directory instead of fetching a module
  copy      copy all the files from a module
  clean     delete imports from your project

Options:
  -f --force     recklessly overwrite files
  -h --help      show help
  --nosync       after reup, skip the sync
  -j N --jobs N  max number of parallel fetches
  -q --quiet     don't print anything
  -v --verbose   print all the things
"""

version_file = os.path.join(compat.MODULE_ROOT, 'VERSION')

commands_map = {}


def command(*subcommand_list):
    def decorator(f):
        coro = asyncio.coroutine(f)
        commands_map[tuple(subcommand_list)] = coro
        return coro
    return decorator


def find_matching_command(args):
    '''If 'peru override add' matches, 'peru override' will also match. Solve
    this by always choosing the longest match. This also means that a command
    like `peru override list`, which has the same effect as the shorter
    `peru override`, doesn't need to be separately implemented.'''
    matches = [(cmds, f) for cmds, f in commands_map.items() if
               all(args[cmd] for cmd in cmds)]
    if not matches:
        return None
    longest_cmds, longest_f = matches[0]
    for cmds, f in matches[1:]:
        if len(cmds) > len(longest_cmds):
            longest_cmds, longest_f = cmds, f
    return longest_f


class Main:
    def run(self, argv, env):
        self.args = parse_argv(argv)

        matching_command = find_matching_command(self.args)
        if matching_command:
            self.runtime = Runtime(self.args, env)
            if not self.args["--quiet"]:
                parser.warn_duplicate_keys(self.runtime.peru_file)
            self.scope, self.imports = parser.parse_file(
                self.runtime.peru_file)
            async.run_task(matching_command(self))
        else:
            if self.args["--version"]:
                print(get_version())
            else:
                # Print the help.
                print(__doc__, end="")

    @command("sync")
    def do_sync(self):
        yield from imports.checkout(
            self.runtime, self.scope, self.imports, self.runtime.root)

    @command('reup')
    def do_reup(self):
        names = self.args['<modules>']
        if not names:
            modules = self.scope.modules.values()
        else:
            modules = self.scope.get_modules_for_reup(names)
        futures = [module.reup(self.runtime) for module in modules]
        yield from async.stable_gather(*futures)
        if not self.args['--nosync']:
            yield from self.do_sync()

    @command("override")
    def do_override(self):
        for module in sorted(self.runtime.overrides):
            print('{}: {}'.format(module, self.runtime.get_override(module)))

    @command("override", "add")
    def do_override_add(self):
        name = self.args['<module>']
        path = self.args['<path>']
        self.runtime.set_override(name, path)

    @command("override", "delete")
    def do_override_delete(self):
        key = self.args['<module>']
        del self.runtime.overrides[key]

    @command('copy')
    def do_copy(self):
        if not self.args['<dest>']:
            dest = tempfile.mkdtemp(prefix='peru_copy_')
        else:
            dest = self.args['<dest>']
        tree = yield from imports.get_tree(
            self.runtime, self.scope, self.args['<target>'])
        self.runtime.cache.export_tree(tree, dest, force=self.runtime.force)
        if not self.args['<dest>']:
            print(dest)

    @command('clean')
    def do_clean(self):
        yield from imports.checkout(
            self.runtime, self.scope, {}, self.runtime.root)


def get_version():
    with open(version_file) as f:
        return f.read().strip()


def parse_argv(argv):
    return docopt.docopt(__doc__, argv, help=False)


def print_red(*args, **kwargs):
    if compat.is_fancy_terminal():
        sys.stdout.write("\x1b[31m")
    print(*args, **kwargs)
    if compat.is_fancy_terminal():
        sys.stdout.write("\x1b[39m")


def main(argv=None, env=None):
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = os.environ.copy()
    try:
        Main().run(argv, env)
    except PrintableError as e:
        if parse_argv(argv)['--verbose']:
            raise  # Just allow the stacktrace to print if verbose.
        print_red(e.message, end='' if e.message.endswith('\n') else '\n')
        sys.exit(1)

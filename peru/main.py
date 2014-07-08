#! /usr/bin/env python3

import os
import sys

import docopt

from . import override
from .cache import Cache
from .compat import makedirs
from .error import PrintableError
from .parser import parse_file
from .resolver import Resolver

__doc__ = """\
Usage:
  peru sync [-fqv]
  peru build [-fqv] [<rules>...]
  peru reup [-qv] (--all | <modules>...)
  peru override [add <module> <path> | delete <module>]
  peru [--help | --version]

Commands:
  sync      apply imports to the working copy
  build     run build rules in the working copy
  reup      get updated module fields from remotes
  override  replace a remote module with a local copy
            (with no arguments, list active overrides)

Options:
  -a --all      reup all modules
  -d --delete   unset an override
  -f --force    sync even when the working copy is dirty
  -h --help     show help
  -q --quiet    don't print anything
  -v --verbose  print all the things
"""

__version__ = "peru 0.1"


commands_map = {}


def command(*subcommand_list):
    def decorator(f):
        commands_map[tuple(subcommand_list)] = f
        return f
    return decorator


def find_matching_command(args):
    """If "peru override add" matches, "peru override" will also match. Solve
    this by always choosing the longest match."""
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
        self.env = env
        self.args = docopt.docopt(__doc__, argv, help=False)

        matching_command = find_matching_command(self.args)
        if matching_command:
            self.setup()
            matching_command(self)
        else:
            if self.args["--version"]:
                print(__version__)
            else:
                # Print the help.
                print(__doc__, end="")

    def setup(self):
        self.peru_file = self.env.get("PERU_FILE", "peru.yaml")
        if not os.path.isfile(self.peru_file):
            raise PrintableError(self.peru_file + " not found")

        self.peru_dir = self.env.get("PERU_DIR", ".peru")
        makedirs(self.peru_dir)
        cache_root = self.env.get("PERU_CACHE",
                                  os.path.join(self.peru_dir, "cache"))
        plugins_root = self.env.get("PERU_PLUGINS_CACHE", None)
        self.cache = Cache(cache_root, plugins_root)
        self.scope, self.local_module = parse_file(self.peru_file)
        self.overrides = override.get_overrides(self.peru_dir)
        self.resolver = Resolver(self.scope, self.cache,
                                 overrides=self.overrides)

    @command("sync")
    def do_sync(self):
        self.local_module.apply_imports(
            self.peru_dir, self.resolver, force=self.args["--force"])

    @command("build")
    def do_build(self):
        self.do_sync()
        rules = self.resolver.get_rules(self.args["<rules>"])
        self.local_module.do_build(rules)

    @command("reup")
    def do_reup(self):
        if self.args["--all"]:
            modules = self.resolver.get_all_modules()
        else:
            modules = self.resolver.get_modules(self.args["<modules>"])
        for module in modules:
            module.reup(self.cache.plugins_root, self.peru_file,
                        quiet=self.args["--quiet"])

    @command("override")
    def do_override(self):
        for module in sorted(self.overrides.keys()):
            print("{}: {}".format(module, self.overrides[module]))

    @command("override", "add")
    def do_override_add(self):
        override.set_override(self.peru_dir, self.args["<module>"],
                              self.args["<path>"])

    @command("override", "delete")
    def do_override_delete(self):
        override.delete_override(self.peru_dir, self.args["<module>"])


def print_red(*args, **kwargs):
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[31m")
    print(*args, **kwargs)
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[39m")


def main(argv=None, env=None):
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = os.environ.copy()
    try:
        Main().run(argv, env)
    except PrintableError as e:
        if e.msg:
            print_red(e.msg)
        sys.exit(1)

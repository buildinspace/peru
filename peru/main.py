#! /usr/bin/env python3

import argparse
import os
import sys

from .cache import Cache
from .error import PrintableError
from .parser import parse_file
from .resolver import Resolver


def build_argparser():
    argparser = argparse.ArgumentParser(
        add_help=False,
        formatter_class=SubcommandHelpFormatter)
    subparsers = argparser.add_subparsers(
        title="commands",
        dest="command",
        metavar="<command>")
    argparser.subcommands = {}

    def add_subcommand(name, help):
        subparser = subparsers.add_parser(name, help=help, add_help=False)
        argparser.subcommands[name] = subparser
        return subparser

    helpcmd = add_subcommand("help", "try `peru help <command>`")
    helpcmd.add_argument("help_target", metavar="<command>", default=None,
                         nargs="?")

    synccmd = add_subcommand(
        "sync", help="fetch, build, and install local imports")
    force_help = "overwrite any changes in the working copy"
    synccmd.add_argument("-f", "--force", action="store_true", help=force_help)

    buildcmd = add_subcommand("build", help="build a local rule, implies sync")
    buildcmd.add_argument(
        "rules", nargs="*", metavar="rule",
        help="name of a rule to build locally, after any default rule")
    buildcmd.add_argument(
        "-f", "--force", action="store_true",
        help="ignore changes in the working copy")

    reupcmd = add_subcommand(
        "reup", help="update peru.yaml with new data from remotes")
    reupcmd.add_argument(
        "modules", nargs="*", metavar="module",
        help="name of module to update")
    reupcmd.add_argument(
        "-a", "--all", action="store_true", help="update all modules")
    reupcmd.add_argument("-q", "--quiet", action="store_true",
                         help="no output on success")

    return argparser


# A hack to get rid of the annoying first entry in the commands help list.
# http://stackoverflow.com/a/13429281/823869
class SubcommandHelpFormatter(argparse.HelpFormatter):
    def _format_action(self, action):
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def fail_no_command(command):
    raise PrintableError('"{}" is not a peru command'.format(command))


class _main:
    def run(self):
        self.argparser = build_argparser()
        self.args = self.argparser.parse_args()
        if self.args.command is None or self.args.command == "help":
            self.help()
            raise PrintableError()

        if self.args.command == "sync":
            self.do_sync()
        elif self.args.command == "build":
            self.do_build()
        elif self.args.command == "reup":
            self.do_reup()
        else:
            fail_no_command(self.args.command)

    def setup(self):
        self.peru_file = os.getenv("PERU_FILE") or "peru.yaml"
        if not os.path.isfile(self.peru_file):
            raise PrintableError(self.peru_file + " not found")

        self.peru_dir = os.getenv("PERU_DIR") or ".peru"
        os.makedirs(self.peru_dir, exist_ok=True)
        cache_root = (os.getenv("PERU_CACHE") or
                      os.path.join(self.peru_dir, "cache"))
        plugins_root = os.getenv("PERU_PLUGINS_CACHE") or None
        self.cache = Cache(cache_root, plugins_root)
        self.scope, self.local_module = parse_file(self.peru_file)
        self.resolver = Resolver(self.scope, self.cache)

    def do_sync(self):
        self.setup()
        self.local_module.apply_imports(
            self.peru_dir, self.resolver, force=self.args.force)

    def do_build(self):
        self.setup()
        self.do_sync()
        rules = self.resolver.get_rules(self.args.rules)
        self.local_module.do_build(rules)

    def do_reup(self):
        if not self.args.all and not self.args.modules:
            self.argparser.subcommands["reup"].print_help()
            raise PrintableError()
        if self.args.all and self.args.modules:
            raise PrintableError("--all cannot be given with explicit modules")
        self.setup()
        if self.args.all:
            modules = self.resolver.get_all_modules()
        else:
            modules = self.resolver.get_modules(self.args.modules)
        for module in modules:
            module.reup(self.cache.plugins_root, self.peru_file,
                        quiet=self.args.quiet)

    def help(self):
        if self.args.command is None or self.args.help_target is None:
            self.argparser.print_help()
            return
        if self.args.help_target not in self.argparser.subcommands:
            fail_no_command(self.args.help_target)
            return
        self.argparser.subcommands[self.args.help_target].print_help()


def print_red(*args, **kwargs):
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[31m")
    print(*args, **kwargs)
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[39m")


def main():
    try:
        _main().run()
    except PrintableError as e:
        if e.msg:
            print_red(e.msg)
        sys.exit(1)

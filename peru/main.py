#! /usr/bin/env python3

import argparse
import os
import sys

from .cache import Cache
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

    return argparser


# A hack to get rid of the annoying first entry in the commands help list.
# http://stackoverflow.com/a/13429281/823869
class SubcommandHelpFormatter(argparse.HelpFormatter):
    def _format_action(self, action):
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def main():
    argparser = build_argparser()
    args = argparser.parse_args()
    if args.command in ("help", None):
        if args.command == "help" and args.help_target is not None:
            if args.help_target not in argparser.subcommands:
                print('"{}" is not a peru command'.format(args.help_target))
            else:
                argparser.subcommands[args.help_target].print_help()
        else:
            argparser.print_help()
        return

    peru_file = os.getenv("PERU_FILE") or "peru.yaml"
    if not os.path.isfile(peru_file):
        print(peru_file + " not found")
        sys.exit(1)
    cache_root = os.getenv("PERU_CACHE") or ".peru-cache"
    plugins_root = os.getenv("PERU_PLUGINS_CACHE")
    cache = Cache(cache_root, plugins_root)
    scope, local_module = parse_file(peru_file)
    resolver = Resolver(scope, cache)

    if args.command in ("sync", "build"):
        local_module.apply_imports(resolver, force=args.force)
    if args.command == "build":
        rules = resolver.get_rules(args.rules)
        local_module.do_build(rules)

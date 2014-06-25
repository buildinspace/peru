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

usage = """\
Usage:
  peru sync [-fqv]
  peru build [-fqv] [RULES...]
  peru reup [-qv] (--all | MODULES...)
  peru override (MODULE PATH | --list | --delete MODULE)
  peru [--help | --version]

Commands:
  sync      apply imports to the working copy
  build     run build rules in the working copy
  reup      get updated module fields from remotes
  override  replace a remote module with a local copy

Options:
  -a --all      reup all modules
  -d --delete   unset an override
  -f --force    sync even when the working copy is dirty
  -h --help     show help
  -l --list     print all active overrides
  -q --quiet    don't print anything
  -v --verbose  print all the things
""".strip()


def fail_no_command(command):
    raise PrintableError('"{}" is not a peru command'.format(command))


class Main:
    def run(self, argv, env):
        self.env = env
        self.args = docopt.docopt(usage, argv, version="peru 0.1")

        commands = ["sync", "build", "reup", "override"]

        for command in commands:
            if self.args[command]:
                self.setup()
                getattr(self, "do_"+command)()
                break
        else:
            print(usage)

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

    def do_sync(self):
        self.local_module.apply_imports(
            self.peru_dir, self.resolver, force=self.args["--force"])

    def do_build(self):
        self.do_sync()
        rules = self.resolver.get_rules(self.args["RULES"])
        self.local_module.do_build(rules)

    def do_reup(self):
        if self.args["--all"]:
            modules = self.resolver.get_all_modules()
        else:
            modules = self.resolver.get_modules(self.args["MODULES"])
        for module in modules:
            module.reup(self.cache.plugins_root, self.peru_file,
                        quiet=self.args["--quiet"])

    def do_override(self):
        if self.args["--list"]:
            for module in sorted(self.overrides.keys()):
                print("{}: {}".format(module, self.overrides[module]))
        elif self.args["--delete"]:
            override.delete_override(self.peru_dir, self.args["MODULE"])
        else:
            override.set_override(self.peru_dir, self.args["MODULE"],
                                  self.args["PATH"])


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

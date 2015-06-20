#! /usr/bin/env python3

import asyncio
import collections
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


__doc__ = '''\
Usage:
    peru [-hqv] [--file=<file>] [--sync-dir=<dir>] [--state-dir=<dir>]
         [--cache-dir=<dir>] [--file-basename=<name>] <command> [<args>...]
    peru [--help|--version]

Commands:
    sync      fetch imports and copy them to your project
    reup      update revision information for your modules
    clean     delete imports from your project
    copy      copy files directly from a module to somewhere else
    override  substitute a local directory for the contents of a module
    help      show help for subcommands, same as -h/--help

Options:
    -h --help             so much help
    -q --quiet            don't print anything
    -v --verbose          print everything

    --file=<file>
        The project file to use instead of 'peru.yaml'. This must be used
        together with --sync-dir.
    --sync-dir=<dir>
        The root directory for your imports, instead of the directory
        containing 'peru.yaml'. This must be used together with --file.
    --state-dir=<dir>
        The directory where peru keeps all of its metadata, including the cache
        and the current imports tree. Defaults to '.peru' next to 'peru.yaml'.
    --cache-dir=<dir>
        The directory for caching all the files peru fetches. Defaults to
        '.peru/cache', or $PERU_CACHE_DIR if it's defined.
    --file-basename=<name>
        An alternative filename (not a path) for 'peru.yaml'. As usual, peru
        will search the current dir and its parents for this file, and import
        paths will be relative to it. Incompatible with --file.
'''


def peru_command(name, doc):
    def decorator(f):
        coro = asyncio.coroutine(f)
        COMMAND_FNS[name] = coro
        COMMAND_DOCS[name] = doc
        return coro
    return decorator

COMMAND_FNS = {}
COMMAND_DOCS = {}


@peru_command('sync', '''\
Usage:
    peru sync [-fhqv] [-j N]

Writes your imports to the sync directory. By default, this is the
directory that contains your peru.yaml file. Peru is normally careful
not to overwrite pre-existing or modified files, and if it detects any
then it writes nothing and reports an error. Use the --force flag if you
want sync to overwrite existing files.

Options:
    -f --force     overwrite existing or changed files
    -h --help      explain these confusing flags
    -j N --jobs N  max number of parallel fetches
    -q --quiet     don't print anything
    -v --verbose   print everything
''')
def do_sync(params):
    yield from imports.checkout(
        params.runtime, params.scope, params.imports, params.runtime.sync_dir)


@peru_command('reup', '''\
Usage:
    peru reup [<modules>...] [-fhqv] [-j N] [--nosync]

Updates each module in your peru.yaml file with the latest revision
information from its source. For git, hg, and svn modules, this is the
`rev` field, and for a curl module it's the `sha1` field. Peru will
either add the field for you, or update it if it's already there. To
update specific modules instead of everything, pass their names as
positional arguments. Normally peru then does a sync, but you can
disable that with --nosync.

Options:
    -f --force     for the sync at the end
    -h --help      what is even happening here?
    --nosync       skip the sync at the end
    -j N --jobs N  max number of parallel fetches
    -q --quiet     don't print anything
    -v --verbose   print everything
''')
def do_reup(params):
    names = params.args['<modules>']
    if not names:
        modules = params.scope.modules.values()
    else:
        modules = params.scope.get_modules_for_reup(names)
    futures = [module.reup(params.runtime) for module in modules]
    yield from async.stable_gather(*futures)
    if not params.args['--nosync']:
        # Do an automatic sync. Reparse peru.yaml to get the new revs.
        new_scope, new_imports = parser.parse_file(params.runtime.peru_file)
        new_params = params._replace(scope=new_scope, imports=new_imports)
        yield from do_sync(new_params)


@peru_command('clean', '''\
Usage:
    peru clean [-fhqv]

Removes any files previously written by sync. As with sync, peru is
cautious about removing files that you have changed. Use --force to
clean changed files.

Options:
    -f --force     allow cleaning modified files
    -h --help      what were they thinking?
    -q --quiet     don't print anything
    -v --verbose   print everything
''')
def do_clean(params):
    yield from imports.checkout(
        params.runtime, params.scope, {}, params.runtime.sync_dir)


@peru_command('copy', '''\
Usage:
    peru copy <target> [<dest>] [-fhqv] [-j N]
    peru copy --help

Writes the contents of a target to a temp dir, or to a destination that
you specify. A target is anything that you can import, so it can be just
a module (foo), a module followed by named rules (foo|bar|baz), or even
a module defined within another module (foo.bing).

Options:
    -f --force     overwrite existing files
    -h --help      is anyone even listening?
    -j N --jobs N  max number of parallel fetches
    -q --quiet     don't print anything
    -v --verbose   print everything
''')
def do_copy(params):
    if not params.args['<dest>']:
        dest = tempfile.mkdtemp(prefix='peru_copy_')
    else:
        dest = params.args['<dest>']
    tree = yield from imports.get_tree(
        params.runtime, params.scope, params.args['<target>'])
    params.runtime.cache.export_tree(tree, dest, force=params.runtime.force)
    if not params.args['<dest>']:
        print(dest)


@peru_command('override', '''\
Usage:
    peru override [list]
    peru override add <module> <path>
    peru override delete <module>
    peru override --help

Adding an override tells peru to use the contents of a given directory
in place of the actual contents of a module. So for example, if your
project normally fetches `foo` from GitHub, but you want to test it with
some changes to `foo` that don't exist upstream, you can override the
`foo` module to with your clone. Then the next time you sync, peru will
use the files from your clone.

Note that override directories are independent of the type of your
module. Peru doesn't care whether you override your git module with an
actual git clone, or just a directory full of files. It simply copies
what's there. Module fields (including `rev`) have no effect while a
module is overridden.

Options:
    -h --help  (>'-')> <('-'<) ^('-')^
''')
def do_override(params):
    if params.args['add']:
        name = params.args['<module>']
        path = params.args['<path>']
        params.runtime.set_override(name, path)
    elif params.args['delete']:
        key = params.args['<module>']
        del params.runtime.overrides[key]
    else:
        for module in sorted(params.runtime.overrides):
            print('{}: {}'.format(module, params.runtime.get_override(module)))


def get_version():
    version_file = os.path.join(compat.MODULE_ROOT, 'VERSION')
    with open(version_file) as f:
        return f.read().strip()


def print_red(*args, **kwargs):
    if compat.is_fancy_terminal():
        sys.stdout.write('\x1b[31m')
    print(*args, **kwargs)
    if compat.is_fancy_terminal():
        sys.stdout.write('\x1b[39m')


def maybe_print_help_and_return(args):
    # `peru --version`
    if args['--version']:
        print(get_version())
        return 0

    help = args['--help']
    command = args['<command>']
    if command == "help":
        help = True
        help_args = args['<args>']
        command = help_args[0] if help_args else None

    # no explicit command, just print toplevel help
    if command is None:
        print(__doc__, end='')
        return 0

    # bad command, or help for a bad command
    if command not in COMMAND_DOCS:
        print(__doc__, end='', file=sys.stderr)
        return 1

    # help for a specific command that actually exists
    if help:
        doc = COMMAND_DOCS.get(command, __doc__)
        print(doc, end='')
        return 0

    # otherwise help is not called for
    return None


def merged_args_dicts(global_args, subcommand_args):
    '''We deal with docopt args from the toplevel peru parse and the subcommand
    parse. We don't want False values for a flag in the subcommand to override
    True values if that flag was given at the top level. This function
    specifically handles that case.'''
    merged = global_args.copy()
    for key, val in subcommand_args.items():
        if key not in merged:
            merged[key] = val
        elif type(merged[key]) is type(val) is bool:
            merged[key] = merged[key] or val
        else:
            raise RuntimeError("Unmergable args.")
    return merged


def docopt_parse_args(argv):
    args = docopt.docopt(__doc__, argv, help=False, options_first=True)
    command = args['<command>']
    if command in COMMAND_DOCS:
        command_doc = COMMAND_DOCS[command]
        command_argv = [command] + args['<args>']
        command_args = docopt.docopt(command_doc, command_argv, help=False)
        args = merged_args_dicts(args, command_args)
    return args


CommandParams = collections.namedtuple(
    'CommandParams', ['args', 'runtime', 'scope', 'imports'])


def main(*, argv=None, env=None, nocatch=False):
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = os.environ.copy()

    args = docopt_parse_args(argv)
    command = args['<command>']

    ret = maybe_print_help_and_return(args)
    if ret is not None:
        return ret

    try:
        runtime = Runtime(args, env)
        if not args['--quiet']:
            parser.warn_duplicate_keys(runtime.peru_file)
        scope, imports = parser.parse_file(runtime.peru_file)
        params = CommandParams(args, runtime, scope, imports)
        command_fn = COMMAND_FNS[command]
        async.run_task(command_fn(params))
    except PrintableError as e:
        if args['--verbose'] or nocatch:
            # Just allow the stacktrace to print if verbose, or in testing.
            raise
        print_red(e.message, end='' if e.message.endswith('\n') else '\n')
        return 1

#! /usr/bin/env python3

import collections
import json
import os
import sys
import tempfile

import docopt

# Unfortunately we need to make sure to keep this import above the others,
# because async_helpers needs to set the global event loop at import time.
from .async_helpers import gather_coalescing_exceptions, run_task

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
    module    get information about the modules in your project
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
        COMMAND_FNS[name] = f
        COMMAND_DOCS[name] = doc
        return f

    return decorator


COMMAND_FNS = {}
COMMAND_DOCS = {}


@peru_command('sync', '''\
Usage:
    peru sync [-fhqv] [-j N] [--no-cache] [--no-overrides]

Writes your imports to the sync directory. By default, this is the
directory that contains your peru.yaml file. Peru is normally careful
not to overwrite pre-existing or modified files, and if it detects any
then it writes nothing and reports an error. Use the --force flag if you
want sync to overwrite existing files.

Options:
    -f --force      overwrite existing or changed files
    -h --help       explain these confusing flags
    -j N --jobs N   max number of parallel fetches
    --no-cache      force modules without exact revs to refetch
    --no-overrides  suppress any `peru override` settings
    -q --quiet      don't print anything
    -v --verbose    print everything
''')
async def do_sync(params):
    params.runtime.print_overrides()
    await imports.checkout(params.runtime, params.scope, params.imports,
                           params.runtime.sync_dir)
    params.runtime.warn_unused_overrides()


@peru_command('reup', '''\
Usage:
    peru reup [<modules>...] [-fhqv] [-j N] [--no-cache] [--no-overrides]
              [--no-sync]

Updates each module in your peru.yaml file with the latest revision
information from its source. For git, hg, and svn modules, this is the
`rev` field, and for a curl module it's the `sha1` field. Peru will
either add the field for you, or update it if it's already there. To
update specific modules instead of everything, pass their names as
positional arguments. Peru does a sync after the reup is done, though
you can prevent that with --no-sync.

Options:
    -f --force      for `peru sync`
    -h --help       what is even happening here?
    --no-cache      for `peru sync`
    --no-overrides  for `peru sync`
    --no-sync       skip the sync at the end
    -j N --jobs N   max number of parallel fetches
    -q --quiet      don't print anything
    -v --verbose    print everything
''')
async def do_reup(params):
    names = params.args['<modules>']
    if not names:
        modules = params.scope.modules.values()
    else:
        modules = params.scope.get_modules_for_reup(names)
    futures = [module.reup(params.runtime) for module in modules]
    await gather_coalescing_exceptions(
        futures, params.runtime.display, verbose=params.runtime.verbose)
    if not params.args['--no-sync']:
        # Do an automatic sync. Reparse peru.yaml to get the new revs.
        new_scope, new_imports = parser.parse_file(params.runtime.peru_file)
        new_params = params._replace(scope=new_scope, imports=new_imports)
        await do_sync(new_params)


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
async def do_clean(params):
    await imports.checkout(params.runtime, params.scope, {},
                           params.runtime.sync_dir)


@peru_command('copy', '''\
Usage:
    peru copy <target> [<dest>] [-fhqv] [-j N] [--no-cache] [--no-overrides]
    peru copy --help

Writes the contents of a target to a temp dir, or to a destination that
you specify. A target is anything that you can import, so it can be just
a module (foo), a module followed by named rules (foo|bar|baz), or even
a module defined within another module (foo.bing).

Options:
    -f --force      overwrite existing files
    -h --help       is anyone even listening?
    -j N --jobs N   max number of parallel fetches
    --no-cache      force modules without exact revs to refetch
    --no-overrides  suppress any `peru override` settings
    -q --quiet      don't print anything
    -v --verbose    print everything
''')
async def do_copy(params):
    params.runtime.print_overrides()
    if not params.args['<dest>']:
        dest = tempfile.mkdtemp(prefix='peru_copy_')
    else:
        dest = params.args['<dest>']
    tree = await imports.get_tree(params.runtime, params.scope,
                                  params.args['<target>'])
    await params.runtime.cache.export_tree(
        tree, dest, force=params.runtime.force)
    if not params.args['<dest>']:
        print(dest)


@peru_command('override', '''\
Usage:
    peru override [list] [--json]
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
    --json     print output as JSON
''')
async def do_override(params):
    overrides = params.runtime.overrides
    if params.args['add']:
        name = params.args['<module>']
        path = params.args['<path>']
        params.runtime.set_override(name, path)
    elif params.args['delete']:
        key = params.args['<module>']
        del overrides[key]
    else:
        if params.args['--json']:
            print(
                json.dumps({
                    module: os.path.abspath(overrides[module])
                    for module in overrides
                }))
        else:
            for module in sorted(overrides):
                print('{}: {}'.format(module,
                                      params.runtime.get_override(module)))


@peru_command('module', '''\
Usage:
    peru module [list] [-h] [--json]

Lists the modules defined in the current project.

Options:
    -h --help  I'm not feeling creative :)
    --json     print output as JSON
''')
async def do_list(params):
    modules = sorted(params.scope.modules.keys())
    if params.args['--json']:
        print(json.dumps(modules))
    else:
        for module in modules:
            print(module)


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
    # Skip further parsing for cases like `peru badcommand` (because there is
    # no docopt), `peru help <cmd>` (because help is a fake command also with
    # no docopt), and `peru --help copy` (because e.g. the copy subcommand
    # does not support calls with no args).
    if command in COMMAND_DOCS and not args['--help']:
        command_doc = COMMAND_DOCS[command]
        command_argv = [command] + args['<args>']
        command_args = docopt.docopt(command_doc, command_argv, help=False)
        args = merged_args_dicts(args, command_args)
    return args


CommandParams = collections.namedtuple('CommandParams',
                                       ['args', 'runtime', 'scope', 'imports'])


def force_utf8_in_ascii_mode_hack():
    '''In systems without a UTF8 locale configured, Python will default to
    ASCII mode for stdout and stderr. This causes our fancy display to fail
    with encoding errors. In particular, you run into this if you try to run
    peru inside of Docker. This is a hack to force emitting UTF8 in that case.
    Hopefully it doesn't break anything important.'''
    if sys.stdout.encoding == 'ANSI_X3.4-1968':
        sys.stdout = open(
            sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)
        sys.stderr = open(
            sys.stderr.fileno(), mode='w', encoding='utf8', buffering=1)


# Called as a setup.py entry point, or from __main__.py (`python3 -m peru`).
def main(*, argv=None, env=None, nocatch=False):
    force_utf8_in_ascii_mode_hack()

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
        runtime = run_task(Runtime(args, env))
        if not args['--quiet']:
            parser.warn_duplicate_keys(runtime.peru_file)
        scope, imports = parser.parse_file(runtime.peru_file)
        params = CommandParams(args, runtime, scope, imports)
        command_fn = COMMAND_FNS[command]
        run_task(command_fn(params))
    except PrintableError as e:
        if args['--verbose'] or nocatch:
            # Just allow the stacktrace to print if verbose, or in testing.
            raise
        print_red(e.message, end='' if e.message.endswith('\n') else '\n')
        return 1

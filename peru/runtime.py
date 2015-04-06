import asyncio
import collections
import os
import tempfile

from . import cache
from . import compat
from .error import PrintableError
from . import display
from .keyval import KeyVal
from . import parser
from . import plugin


class Runtime:
    def __init__(self, args, env):
        self._set_paths(args, env)

        compat.makedirs(self.state_dir)
        self.cache = cache.Cache(self.cache_dir)

        self._tmp_root = os.path.join(self.state_dir, 'tmp')
        compat.makedirs(self._tmp_root)

        self.overrides = KeyVal(os.path.join(self.state_dir, 'overrides'),
                                self._tmp_root)

        self.force = args.get('--force', False)
        if args['--quiet'] and args['--verbose']:
            raise PrintableError(
                "Peru can't be quiet and verbose at the same time.")
        self.quiet = args['--quiet']
        self.verbose = args['--verbose']

        # Use a semaphore (a lock that allows N holders at once) to limit the
        # number of fetches that can run in parallel.
        num_fetches = _get_parallel_fetch_limit(args)
        self.fetch_semaphore = asyncio.BoundedSemaphore(num_fetches)

        # Use locks to make sure the same cache keys don't get double fetched.
        self.cache_key_locks = collections.defaultdict(asyncio.Lock)

        # Use a different set of locks to make sure that plugin cache dirs are
        # only used by one job at a time.
        self.plugin_cache_locks = collections.defaultdict(asyncio.Lock)

        self.display = get_display(args)

    def _set_paths(self, args, env):
        getter = ArgsEnvGetter(args, env)
        explicit_peru_file = getter.get('--peru-file', 'PERU_FILE')
        explicit_sync_dir = getter.get('--sync-dir', 'PERU_SYNC_DIR')
        if (explicit_peru_file is None) != (explicit_sync_dir is None):
            raise PrintableError(
                'If the peru file or the sync dir is set, the other must also '
                'be set.')
        if explicit_peru_file:
            self.peru_file = explicit_peru_file
            self.sync_dir = explicit_sync_dir
        else:
            self.peru_file = find_peru_file(
                os.getcwd(), parser.DEFAULT_PERU_FILE_NAME)
            self.sync_dir = os.path.dirname(self.peru_file)
        self.state_dir = (getter.get('--state-dir', 'PERU_STATE_DIR') or
                          os.path.join(self.sync_dir, '.peru'))
        self.cache_dir = (getter.get('--cache-dir', 'PERU_CACHE_DIR') or
                          os.path.join(self.state_dir, 'cache'))

    def tmp_dir(self):
        dir = tempfile.TemporaryDirectory(dir=self._tmp_root)
        return dir

    def set_override(self, name, path):
        if not os.path.isabs(path):
            # We can't store relative paths as given, because peru could be
            # running from a different working dir next time. But we don't want
            # to absolutify everything, because the user might want the paths
            # to be relative (for example, so a whole workspace can be moved as
            # a group while preserving all the overrides). So reinterpret all
            # relative paths from the project root.
            path = os.path.relpath(path, start=self.sync_dir)
        self.overrides[name] = path

    def get_override(self, name):
        if name not in self.overrides:
            return None
        path = self.overrides[name]
        if not os.path.isabs(path):
            # Relative paths are stored relative to the project root.
            # Reinterpret them relative to the cwd. See the above comment in
            # set_override.
            path = os.path.relpath(os.path.join(self.sync_dir, path))
        return path

    def get_plugin_context(self):
        return plugin.PluginContext(
            # Plugin cwd is always the directory containing peru.yaml, even if
            # the sync_dir has been explicitly set elsewhere. That's because
            # relative paths in peru.yaml should respect the location of that
            # file.
            cwd=os.path.dirname(self.peru_file),
            plugin_cache_root=self.cache.plugins_root,
            parallelism_semaphore=self.fetch_semaphore,
            plugin_cache_locks=self.plugin_cache_locks,
            tmp_root=self._tmp_root)


def find_peru_file(start_dir, name):
    '''Walk up the directory tree until we find a file of the given name.'''
    prefix = os.path.abspath(start_dir)
    while True:
        candidate = os.path.join(prefix, name)
        if os.path.isfile(candidate):
            return candidate
        if os.path.exists(candidate):
            raise PrintableError(
                "Found {}, but it's not a file.".format(candidate))
        if os.path.dirname(prefix) == prefix:
            # We've walked all the way to the top. Bail.
            raise PrintableError("Can't find " + name)
        # Not found at this level. We must go...shallower.
        prefix = os.path.dirname(prefix)


def _get_parallel_fetch_limit(args):
    jobs = args.get('--jobs')
    if jobs is None:
        return plugin.DEFAULT_PARALLEL_FETCH_LIMIT
    try:
        parallel = int(jobs)
        if parallel <= 0:
            raise PrintableError('Argument to --jobs must be 1 or more.')
        return parallel
    except:
        raise PrintableError('Argument to --jobs must be a number.')


def get_display(args):
    if args['--quiet']:
        return display.QuietDisplay()
    elif args['--verbose']:
        return display.VerboseDisplay()
    elif compat.is_fancy_terminal():
        return display.FancyDisplay()
    else:
        return display.QuietDisplay()


class ArgsEnvGetter:
    def __init__(self, args, env):
        self.args = args
        self.env = env

    def get(self, flag_name, env_name):
        if self.args.get(flag_name):
            return self.args.get(flag_name)
        if self.env.get(env_name):
            return self.env.get(env_name)
        return None

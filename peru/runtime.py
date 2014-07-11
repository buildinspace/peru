import os
import tempfile

from . import cache
from . import compat
from .error import PrintableError
from . import override
from . import parser


class Runtime:
    def __init__(self, args, env):
        peru_file_name = env.get('PERU_FILE_NAME', 'peru.yaml')
        self.peru_file = find_peru_file(os.getcwd(), peru_file_name)

        self.work_dir = os.path.dirname(self.peru_file)

        self.peru_dir = env.get(
            'PERU_DIR', os.path.join(self.work_dir, '.peru'))
        compat.makedirs(self.peru_dir)

        self.scope, self.local_module = parser.parse_file(
            self.peru_file, peru_dir=self.peru_dir)

        cache_dir = env.get('PERU_CACHE', os.path.join(self.peru_dir, 'cache'))
        self.cache = cache.Cache(cache_dir)

        self._tmp_root = os.path.join(self.peru_dir, 'tmp')
        compat.makedirs(self._tmp_root)

        self.overrides = override.get_overrides(self.peru_dir)

        self.force = args['--force']
        if args['--quiet'] and args['--verbose']:
            raise PrintableError(
                "Peru can't be quiet and loud at the same time.\n"
                "Have you tried using <blink>?")
        self.quiet = args['--quiet']
        self.verbose = args['--verbose']

    def tmp_dir(self):
        dir = tempfile.TemporaryDirectory(dir=self._tmp_root)
        return dir


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

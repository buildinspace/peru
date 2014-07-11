import os
import tempfile

from . import cache
from . import compat
from . import error
from . import override
from . import parser


class Runtime:
    def __init__(self, args, env):
        self.peru_file = env.get('PERU_FILE', 'peru.yaml')
        if not os.path.isfile(self.peru_file):
            raise error.PrintableError(self.peru_file + ' not found')

        self.scope, self.local_module = parser.parse_file(self.peru_file)

        self.peru_dir = env.get('PERU_DIR', '.peru')
        compat.makedirs(self.peru_dir)

        cache_dir = env.get('PERU_CACHE', os.path.join(self.peru_dir, 'cache'))
        self.cache = cache.Cache(cache_dir)

        self._tmp_root = os.path.join(self.peru_dir, 'tmp')
        compat.makedirs(self._tmp_root)

        self.overrides = override.get_overrides(self.peru_dir)

        self.force = args['--force']
        if args['--quiet'] and args['--verbose']:
            raise error.PrintableError(
                "Peru can't be quiet and loud at the same time.\n"
                "Have you tried using <blink>?")
        self.quiet = args['--quiet']
        self.verbose = args['--verbose']

    def tmp_dir(self):
        dir = tempfile.TemporaryDirectory(dir=self._tmp_root)
        return dir

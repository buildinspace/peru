import os
import tempfile

from . import cache
from . import compat
from .error import PrintableError
from .keyval import KeyVal
from . import parser


class Runtime:
    def __init__(self, args, env):
        peru_file_name = env.get('PERU_FILE_NAME', 'peru.yaml')
        self.peru_file = find_peru_file(os.getcwd(), peru_file_name)

        self.root = os.path.dirname(self.peru_file)

        self.peru_dir = env.get(
            'PERU_DIR', os.path.join(self.root, '.peru'))
        compat.makedirs(self.peru_dir)

        parse_result = parser.parse_file(
            self.peru_file, peru_dir=self.peru_dir)
        self.scope = parse_result.scope
        self.local_module = parse_result.local_module
        self.plugin_roots = tuple(os.path.join(self.root, path)
                                  for path in parse_result.plugin_paths)

        cache_dir = env.get('PERU_CACHE', os.path.join(self.peru_dir, 'cache'))
        self.cache = cache.Cache(cache_dir)

        self._tmp_root = os.path.join(self.peru_dir, 'tmp')
        compat.makedirs(self._tmp_root)

        self.overrides = KeyVal(os.path.join(self.peru_dir, 'overrides'),
                                self._tmp_root)

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

    def set_override(self, name, path):
        if not os.path.isabs(path):
            # We can't store relative paths as given, because peru could be
            # running from a different working dir next time. But we don't want
            # to absolutify everything, because the user might want the paths
            # to be relative (for example, so a whole workspace can be moved as
            # a group while preserving all the overrides). So reinterpret all
            # relative paths from the project root.
            path = os.path.relpath(path, start=self.root)
        self.overrides[name] = path

    def get_override(self, name):
        path = self.overrides[name]
        if not os.path.isabs(path):
            # Relative paths are stored relative to the project root.
            # Reinterpret them relative to the cwd. See the above comment in
            # set_override.
            path = os.path.relpath(os.path.join(self.root, path))
        return path


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

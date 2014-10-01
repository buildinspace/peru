import asyncio
from pathlib import Path
import os
import subprocess
import textwrap

from .async import create_subprocess_with_handle
from .cache import compute_key
from .error import PrintableError


class Rule:
    def __init__(self, name, build_command, export, files):
        self.name = name
        self.build_command = build_command
        self.export = export
        self.files = files

    def _cache_key(self, input_tree):
        return compute_key({
            'input_tree': input_tree,
            'build': self.build_command,
            'export': self.export,
            'files': self.files,
        })

    @asyncio.coroutine
    def do_build(self, runtime, path):
        """Executes the rule and returns the exported directory."""
        if self.build_command:
            # Take a global lock to prevent more than one build command from
            # running at once. This is both to prevent thrashing the disk, and
            # to avoid interleaving output. The printing handle obtained here
            # lets the build print straight to the console above the fancy
            # display.
            with (yield from runtime.build_lock):
                try:
                    yield from create_subprocess_with_handle(
                        self.build_command,
                        runtime.display.get_printing_handle(),
                        cwd=path, shell=True)
                except subprocess.CalledProcessError as e:
                    raise BuildCommandRuntimeError(e)
        if self.export:
            export_path = os.path.join(path, self.export)
            if not os.path.exists(export_path):
                raise PrintableError(
                    "export path for rule '{}' does not exist: {}".format(
                        self.name, export_path))
            if not os.path.isdir(export_path):
                raise PrintableError(
                    "export path for rule '{}' is not a directory: {}"
                    .format(self.name, export_path))
            return export_path
        else:
            return path

    @asyncio.coroutine
    def get_tree(self, runtime, input_tree):
        key = self._cache_key(input_tree)

        # As with RemoteModule, take a lock on the cache key to avoid building
        # the same rule (or identical rules) twice with the same input.
        # NB: It might look like this lock isn't necessary, because we take a
        # global build lock in do_build() too. But don't be fooled! This lock
        # has to be here *before* the cache check, to ensure that subsequent
        # copies of the same rule get their cache hits, rather than blowing by
        # the check and just waiting inside of do_build() to do repeat work.
        cache_lock = runtime.cache_key_locks[key]
        with (yield from cache_lock):
            if key in runtime.cache.keyval:
                return runtime.cache.keyval[key]

            with runtime.tmp_dir() as tmp_dir:
                runtime.cache.export_tree(input_tree, tmp_dir)
                export_dir = yield from self.do_build(runtime, tmp_dir)
                files = self._get_files(export_dir)
                tree = runtime.cache.import_tree(export_dir, files)

            runtime.cache.keyval[key] = tree

        return tree

    def _get_files(self, export_path):
        if not self.files:
            return None
        all_files = set()
        for glob in self.files:
            matches = set(str(match.relative_to(export_path))
                          for match in Path(export_path).glob(glob))
            if not matches:
                raise NoMatchingFilesError(
                    'No matches for path "{}".'.format(glob))
            all_files |= matches
        return all_files


class NoMatchingFilesError(PrintableError):
    pass


class BuildCommandRuntimeError(PrintableError):
    def __init__(self, error):
        super().__init__(textwrap.dedent('''\
            Error in build command: {}
            Return code: {}
            Output:
            {}''').format(error.cmd, error.returncode, error.output))

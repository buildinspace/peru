import asyncio
from pathlib import Path
import os

from .cache import compute_key
from .error import PrintableError


class Rule:
    def __init__(self, name, export, files, pick):
        self.name = name
        self.export = export
        self.files = files
        self.pick = pick

    def _cache_key(self, input_tree):
        return compute_key({
            'input_tree': input_tree,
            'export': self.export,
            'files': self.files,
            'pick': self.pick
        })

    def _get_export_path(self, runtime, module_root):
        if self.export:
            export_path = os.path.join(module_root, self.export)
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
            return module_root

    @asyncio.coroutine
    def get_tree(self, runtime, input_tree):
        key = self._cache_key(input_tree)

        # As with Module, take a lock on the cache key to avoid running the
        # same rule (or identical rules) twice with the same input.
        cache_lock = runtime.cache_key_locks[key]
        with (yield from cache_lock):
            if key in runtime.cache.keyval:
                return runtime.cache.keyval[key]

            with runtime.tmp_dir() as tmp_dir:
                runtime.cache.export_tree(input_tree, tmp_dir)
                export_path = self._get_export_path(runtime, tmp_dir)
                files = self._get_files(export_path) or set()
                files |= self._get_picked_files(tmp_dir, export_path) or set()
                tree = runtime.cache.import_tree(export_path, files)

            runtime.cache.keyval[key] = tree

        return tree

    def _get_files(self, export_path):
        if not self.files:
            return None
        files = set()
        for glob in self.files:
            matches = set(str(match.relative_to(export_path))
                          for match in Path(export_path).glob(glob))
            if not matches:
                raise NoMatchingFilesError(
                    'No matches for "{}".'.format(glob))
            files |= matches
        return files

    def _get_picked_files(self, module_root, export_path):
        if not self.pick:
            return None
        files = set()
        for glob in self.pick:
            matches = set(match for match in Path(module_root).glob(glob))
            if not matches:
                raise NoMatchingFilesError(
                    'No matches for "{}".'.format(glob))
            # Exlude matches whose parents do not contain the export path.
            matches = set(str(match.relative_to(export_path))
                          for match in matches
                          if Path(export_path) in match.parents)
            if not matches:
                raise NoMatchingFilesError(
                    'Matches found for "{}", but none are beneath the export '
                    'path "{}".'.format(glob, export_path))
            files |= matches
        return files


class NoMatchingFilesError(PrintableError):
    pass

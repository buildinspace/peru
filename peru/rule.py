import asyncio
from pathlib import Path, PurePosixPath
import os
import stat

from .cache import compute_key, TREE_TYPE
from .error import PrintableError


class Rule:
    def __init__(self, name, copy, move, executable, pick, export, files):
        self.name = name
        self.copy = copy
        self.move = move
        self.executable = executable
        self.pick = pick
        self.export = export
        self.files = files

    def _cache_key(self, input_tree):
        return compute_key({
            'input_tree': input_tree,
            'copy': self.copy,
            'move': self.move,
            'executable': self.executable,
            'pick': self.pick,
            'export': self.export,
            'files': self.files,
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

            tree = input_tree
            if self.copy:
                tree = copy_files(runtime.cache, tree, self.copy)
            if self.move:
                tree = move_files(runtime.cache, tree, self.move)
            with runtime.tmp_dir() as tmp_dir:
                runtime.cache.export_tree(tree, tmp_dir)
                self._chmod_executables(tmp_dir)
                export_path = self._get_export_path(runtime, tmp_dir)
                files = self._get_files(export_path) or set()
                files |= self._get_picked_files(tmp_dir, export_path) or set()
                tree = runtime.cache.import_tree(export_path, files)

            runtime.cache.keyval[key] = tree

        return tree

    def _chmod_executables(self, module_root):
        root_path = Path(module_root)
        for glob in self.executable:
            paths = root_path.glob(glob)
            if not paths:
                raise NoMatchingFilesError(
                    'No matches for executable path "{}".'.format(glob))
            for path in paths:
                # We don't check whether the path is a file or a directory.
                # `chmod +x` on a directory should generally be a no-op, and in
                # any case git doesn't represent directory permissions in
                # trees.
                new_mode = (path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP |
                            stat.S_IXOTH)
                path.chmod(new_mode)

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


def _copy_files_modifications(_cache, tree, paths_multimap):
    modifications = {}
    for source in paths_multimap:
        source_info_dict = _cache.ls_tree(tree, source)
        if not source_info_dict:
            raise NoMatchingFilesError(
                'Path "{}" does not exist.'.format(source))
        source_info = list(source_info_dict.items())[0][1]
        for dest in paths_multimap[source]:
            # If dest is a directory, put the source inside dest instead of
            # overwriting dest entirely.
            dest_is_dir = False
            dest_info_dict = _cache.ls_tree(tree, dest)
            if dest_info_dict:
                dest_info = list(dest_info_dict.items())[0][1]
                dest_is_dir = (dest_info.type == TREE_TYPE)
            adjusted_dest = dest
            if dest_is_dir:
                adjusted_dest = str(PurePosixPath(dest) /
                                    PurePosixPath(source).name)
            modifications[adjusted_dest] = source_info
    return modifications


def copy_files(_cache, tree, paths_multimap):
    modifications = _copy_files_modifications(_cache, tree, paths_multimap)
    return _cache.modify_tree(tree, modifications)


def move_files(_cache, tree, paths_multimap):
    # First obtain the copies from the original tree. Moves are not ordered but
    # happen all at once, so if you move a->b and b->c, the contents of c will
    # always end up being b rather than a.
    modifications = _copy_files_modifications(_cache, tree, paths_multimap)
    # Now add in deletions, but be careful not to delete a file that just got
    # moved. Note that if "a" gets moved into "dir", it will end up at "dir/a",
    # even if "dir" is deleted (because modify_tree always modifies parents
    # before decending into children, and deleting a dir is a modification of
    # that dir's parent).
    for source in paths_multimap:
        if source not in modifications:
            modifications[source] = None
    return _cache.modify_tree(tree, modifications)


class NoMatchingFilesError(PrintableError):
    pass

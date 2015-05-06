import collections
import hashlib
import json
import os
import pathlib
import re
import subprocess

from .compat import makedirs
from .error import PrintableError
from .keyval import KeyVal


def compute_key(data):
    # To hash this dictionary of fields, serialize it as a JSON string, and
    # take the SHA1 of that string. Dictionary key order is unspecified, so
    # "sort_keys" keeps our hash stable. Specifying separators makes the
    # JSON slightly more compact, and protects us against changes in the
    # default.  "ensure_ascii" defaults to true, so specifying it just
    # protects us from changes in the default.
    json_representation = json.dumps(
        data, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    sha1 = hashlib.sha1()
    sha1.update(json_representation.encode("utf8"))
    return sha1.hexdigest()


class Cache:
    def __init__(self, root):
        self.root = root
        self.plugins_root = os.path.join(root, "plugins")
        # Don't freak out if plugins_root has nonstandard permissions.
        if not os.path.exists(self.plugins_root):
            os.makedirs(self.plugins_root)
        self.tmp_path = os.path.join(root, "tmp")
        makedirs(self.tmp_path)
        self.keyval = KeyVal(os.path.join(root, 'keyval'), self.tmp_path)
        self.trees_path = os.path.join(root, "trees")
        self._empty_tree = None
        self._init_trees()

    def _init_trees(self):
        if not os.path.exists(self.trees_path):
            os.makedirs(self.trees_path)
            self._git('init', '--bare')

    class GitError(RuntimeError):
        def __init__(self, command, output, errorcode):
            self.command = " ".join(command)
            self.output = output
            self.errorcode = errorcode
            message = 'git command "{}" returned error code {}:\n{}'.format(
                self.command,
                self.errorcode,
                self.output)
            RuntimeError.__init__(self, message)

    def _git(self, *args, work_tree=None, input=None, text=True):
        command = ["git"]
        command.append("--git-dir=" + self.trees_path)
        if work_tree:
            command.append("--work-tree=" + work_tree)
        command.extend(args)
        process = subprocess.Popen(
            command,
            env=self._git_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=text)
        output, _ = process.communicate(input=input)
        if text:
            output = output.rstrip()
        if process.returncode != 0:
            raise self.GitError(command, output, process.returncode)
        return output

    # Prevents git from reading any global configs.
    def _git_env(self):
        vars_to_delete = ["HOME", "XDG_CONFIG_HOME"]
        env = dict(os.environ)
        for var in vars_to_delete:
            if var in env:
                del env[var]
        env["GIT_CONFIG_NOSYSTEM"] = "true"
        return env

    def get_empty_tree(self):
        if not self._empty_tree:
            self._git('read-tree', '--empty')
            self._empty_tree = self._git('write-tree')
        return self._empty_tree

    def import_tree(self, src, *, picks=None, excludes=None):
        if not os.path.exists(src):
            raise RuntimeError('import tree called on nonexistent path ' + src)
        self._git('read-tree', '--empty')  # clear the index for safety
        # Use --force to avoid .gitignore rules. We shouldn't respect them.
        if picks:
            self._git('add', '--force', '--', *picks, work_tree=src)
        else:
            self._git('add', '--all', '--force', work_tree=src)
        self._remove_matching_files_from_index(src, excludes)
        tree = self._git('write-tree')
        return tree

    def merge_trees(self, base_tree, merge_tree, merge_path='.'):
        if base_tree:
            self._git('read-tree', base_tree)
        else:
            self._git('read-tree', '--empty')

        # The --prefix argument to read-tree chokes on paths that contain dot
        # or dot-dot. Instead of './', it wants the empty string. Oblige it.
        # NOTE: This parameter *must* be forward-slash-separated, even on
        # Windows. os.path.normpath() is not correct here!
        merge_path_obj = pathlib.PurePosixPath(merge_path)
        assert '..' not in merge_path_obj.parts
        prefix = merge_path_obj.as_posix()
        prefix = '' if prefix == '.' else prefix

        # The git docs say that a --prefix value must end in a slash. That
        # doesn't seem to be true in practice, but better safe than sorry. Note
        # that git treats '--prefix=/' as the root of the tree, so this doesn't
        # break that case.
        if not prefix.endswith('/'):
            prefix += '/'

        # Normally read-tree with --prefix wants to make sure changes don't
        # stomp on the working copy. The -i flag tells it to pretend the
        # working copy doesn't exist. (Which is important, because we don't
        # have one right now!)
        try:
            self._git('read-tree', '-i', '--prefix', prefix, merge_tree)
        except self.GitError as e:
            raise MergeConflictError(e.output) from e

        unified_tree = self._git('write-tree')
        return unified_tree

    # TODO: Use temporary index files for everything in Cache.
    def export_tree(self, tree, dest, previous_tree=None, *, force=False):
        tree = tree or self.get_empty_tree()
        previous_tree = previous_tree or self.get_empty_tree()

        if not os.path.exists(dest):
            os.makedirs(dest)

        self._read_tree_and_error_on_modified(previous_tree, dest, force)

        # Check out the new tree using read-tree's -u flag. This cleans up
        # deleted files for us, and (without --reset) refuses to stomp on
        # existing files.
        if force:
            self._git('read-tree', '--reset', '-u', tree, work_tree=dest)
        else:
            try:
                self._git('read-tree', '-m', '-u', tree, work_tree=dest)
            except self.GitError:
                self._error_on_preexisting_files(previous_tree, tree, dest)
                raise  # If it wasn't related to preexisting files, rethrow.

        # Recreate any missing files.
        self._git('checkout-index', '--all', work_tree=dest)

    def _read_tree_and_error_on_modified(self, tree, dest, force):
        self._read_tree(tree, dest)
        # We allow deleted files, and the -m flag skips them for us.
        modified_output = self._git(
            'diff-index', '-m', '-z', '--name-only', tree,
            work_tree=dest)
        modified = [name for name in modified_output.split('\x00') if name]
        if modified and not force:
            raise DirtyWorkingCopyError(
                'Imported files have been modified ' +
                '(use --force to overwrite):\n\n' +
                _format_file_lines(modified))

    def _read_tree(self, tree, dest):
        # Read previous_tree into the index.
        self._git('read-tree', tree)
        # Refresh all the stat() information in the index.
        try:
            # This throws an error on modified files. Suppress it.
            self._git('update-index', '--refresh', work_tree=dest)
        except self.GitError as e:
            if 'needs update' not in e.output:
                # Reraise any errors we don't recognize.
                raise

    def _error_on_preexisting_files(self, previous_tree, tree, dest):
        added_files_output = self._git(
            'diff-tree', '--diff-filter=A', '--name-only', '-r', '-z',
            previous_tree, tree)
        added_files = added_files_output.split('\x00')
        existing_added_files = [f for f in added_files if f and
                                os.path.exists(os.path.join(dest, f))]
        existing_added_files.sort()
        if existing_added_files:
            raise DirtyWorkingCopyError(
                'Imports would overwrite preexisting files '
                '(use --force to write anyway):\n\n' +
                _format_file_lines(existing_added_files))

    def read_file(self, tree, path):
        # TODO: Make this handle symlinks in the tree.

        # --full-tree makes ls-tree ignore the cwd
        ls_output = self._git('ls-tree', '--full-tree', '-z', tree, path)
        ls_lines = ls_output.strip('\x00').split('\x00')
        # Remove empty lines.
        ls_lines = list(filter(None, ls_lines))
        if len(ls_lines) == 0:
            raise FileNotFoundError('Path "{}" not found in tree {}.'
                                    .format(path, tree))
        assert len(ls_lines) == 1
        mode, type, sha1, name = ls_lines[0].split()
        if type == 'tree':
            raise IsADirectoryError('Path "{}" in tree {} is a directory.'
                                    .format(path, tree))
        assert type == 'blob'
        file_bytes = self._git('cat-file', '-p', sha1, text=False)
        return file_bytes

    def _remove_matching_files_from_index(self, workdir, paths):
        if not paths:
            return
        ls_files_output = self._git('ls-files', '--full-name', '-z', *paths)
        self._git('update-index', '--force-remove', '-z', '--stdin',
                  work_tree=workdir, input=ls_files_output)

    def ls_tree(self, tree, path=None, *, recursive=False):
        # Lines in ls-tree are of the following form (note that the wide space
        # is a tab):
        # 100644 blob a2b67564ae3a7cb3237ee0ef1b7d26d70f2c213f    README.md
        entry_regex = r'(\w+) (\w+) (\w+)\t(.*)'
        command = ['ls-tree', '-z', tree]
        if path is not None:
            canonical_path = str(pathlib.PurePosixPath(path))
            command += [canonical_path]
        if recursive:
            # -t means tree entries are included in the listing.
            command += ['-r', '-t']
        output = self._git(*command)
        if not output:
            return {}
        entries = {}
        for line in output.strip('\x00').split('\x00'):
            mode, type, hash, name = re.match(entry_regex, line).groups()
            if (recursive and path is not None and
                    len(name) < len(canonical_path) and type == TREE_TYPE):
                # In recursive mode, leave out the parents of the target dir.
                continue
            entries[name] = TreeEntry(mode, type, hash)
        return entries

    def _mktree(self, entries):
        entry_format = '{} {} {}\t{}'
        input = '\x00'.join(entry_format.format(mode, type, hash, name)
                            for name, (mode, type, hash) in entries.items())
        tree = self._git('mktree', '-z', input=input)
        return tree

    def modify_tree(self, tree, modifications):
        '''The modifications are a map of the form, {path: TreeEntry}. The tree
        can be None to indicate an empty starting tree. The entries can be
        either blobs or trees, or None to indicate a deletion. The return value
        is either the hash of the resulting tree, or None if the resulting tree
        is empty. Modifications in parent directories are done before
        modifications in subdirectories below them, so for example you can
        insert a tree at a given path and also insert more new stuff beneath
        that path, without fear of overwriting the new stuff.'''

        # Read the original contents of the base tree.
        entries = self.ls_tree(tree, '.') if tree is not None else {}

        # Separate the modifications into two groups, those that refer to
        # entries at the base of this tree (e.g. 'foo'), and those that refer
        # to entries in subtrees (e.g. 'foo/bar').
        modifications_at_base = dict()
        modifications_in_subtrees = collections.defaultdict(dict)
        for path_str, entry in modifications.items():
            # Canonicalize paths to get rid of duplicate/trailing slashes.
            path = pathlib.PurePosixPath(path_str)

            # Check for nonsense paths.
            # TODO: Maybe stop recursive calls from repeating these checks.
            if len(path.parts) == 0:
                raise ModifyTreeError('Cannot modify an empty path.')
            elif path.parts[0] == '/':
                raise ModifyTreeError('Cannot modify an absolute path.')
            elif '..' in path.parts:
                raise ModifyTreeError('.. is not allowed in tree paths.')

            if len(path.parts) == 1:
                modifications_at_base[str(path)] = entry
            else:
                first_dir = path.parts[0]
                rest = str(pathlib.PurePosixPath(*path.parts[1:]))
                modifications_in_subtrees[first_dir][rest] = entry

        # Insert or delete entries in the base tree. Note that this happens
        # before any subtree operations.
        for name, entry in modifications_at_base.items():
            if entry is None:
                entries.pop(name, None)
            else:
                entries[name] = entry

        # Recurse to compute modified subtrees. Note how we handle deletions:
        # If 'a' is a file, inserting a new file at 'a/b' will implicitly
        # delete 'a', but trying to delete 'a/b' will be a no-op and will not
        # delete 'a'.
        for name, sub_modifications in modifications_in_subtrees.items():
            subtree_base = None
            if name in entries and entries[name].type == TREE_TYPE:
                subtree_base = entries[name].hash
            new_subtree = self.modify_tree(subtree_base, sub_modifications)
            if new_subtree is not None:
                entries[name] = TreeEntry(TREE_MODE, TREE_TYPE, new_subtree)
            # Delete an empty tree if it was actually a tree to begin with.
            elif name in entries and entries[name].type == TREE_TYPE:
                del entries[name]

        # Return the resulting tree, or None if empty.
        if entries:
            return self._mktree(entries)
        else:
            return None


def _format_file_lines(files):
    '''Given a list of filenames that we're about to print, limit it to a
    reasonable number of lines.'''
    LINES_TO_SHOW = 10
    if len(files) <= LINES_TO_SHOW:
        lines = '\n'.join(files)
    else:
        lines = ('\n'.join(files[:LINES_TO_SHOW-1]) +
                 '\n...{} total'.format(len(files)))
    return lines


class ModifyTreeError(PrintableError):
    pass


class DirtyWorkingCopyError(PrintableError):
    pass


class MergeConflictError(PrintableError):
    pass

TreeEntry = collections.namedtuple('TreeEntry', ['mode', 'type', 'hash'])

BLOB_TYPE = 'blob'
TREE_TYPE = 'tree'

NONEXECUTABLE_FILE_MODE = '100644'
EXECUTABLE_FILE_MODE = '100755'
TREE_MODE = '040000'

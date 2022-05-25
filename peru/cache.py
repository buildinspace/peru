import asyncio
import contextlib
import collections
import hashlib
import json
import os
import pathlib
import re
import textwrap

from .async_helpers import safe_communicate
from .compat import makedirs
from .error import PrintableError
from .keyval import KeyVal

# git output modes
TEXT_MODE = object()
BINARY_MODE = object()

# for tests
DEBUG_GIT_COMMAND_COUNT = 0


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


class GitSession:
    '''All of our git operations will share the same repo, but we don't want
    them to share the same index file. That's for two reasons:
      1) We want to be able to run multiple operations in parallel that write
         to the index file.
      2) We want to be able to save the index file corresponding to the last
         imports, and guarantee that nothing will touch it.
    A git session owns the index file it does operations on. We also use this
    class to abstract away the low level details of git command flags. (And in
    the future, this could be where we plug in libgit2.)'''

    def __init__(self, git_dir, index_file, working_copy):
        self.git_dir = git_dir
        self.index_file = index_file
        self.working_copy = working_copy

    async def git(self, *args, input=None, output_mode=TEXT_MODE, cwd=None):
        global DEBUG_GIT_COMMAND_COUNT
        DEBUG_GIT_COMMAND_COUNT += 1
        command = ['git']
        command.append('--git-dir=' + self.git_dir)
        if self.working_copy:
            command.append("--work-tree=" + self.working_copy)
        command.extend(args)
        if isinstance(input, str):
            input = input.encode()
        process = await asyncio.subprocess.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=self.git_env(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await safe_communicate(process, input)
        stderr = stderr.decode()
        if output_mode == TEXT_MODE:
            stdout = stdout.decode()
            stdout = stdout.rstrip()
        if process.returncode != 0:
            raise GitError(command, process.returncode, stdout, stderr)
        return stdout

    def git_env(self):
        'Set the index file and prevent git from reading global configs.'
        env = dict(os.environ)
        for var in ["HOME", "XDG_CONFIG_HOME"]:
            env.pop(var, None)
        env["GIT_CONFIG_NOSYSTEM"] = "true"
        # Weirdly, GIT_INDEX_FILE is interpreted relative to the work tree. As
        # a workaround, we absoluteify the path.
        env["GIT_INDEX_FILE"] = os.path.abspath(self.index_file)
        return env

    async def init_git_dir(self):
        await self.git('init', '--bare')

    async def read_tree_into_index(self, tree):
        await self.git('read-tree', tree)

    async def read_tree_and_stats_into_index(self, tree):
        await self.read_tree_into_index(tree)
        # Refresh all the stat() information in the index.
        try:
            # This throws an error on modified files. Suppress it.
            await self.git('update-index', '--refresh')
        except GitError as e:
            if 'needs update' not in e.stdout:
                # Reraise any errors we don't recognize.
                raise

    async def make_tree_from_index(self):
        tree = await self.git('write-tree')
        return tree

    async def read_working_copy_into_index(self, picks):
        # Use --force to avoid .gitignore rules. We shouldn't respect them.
        if picks:
            # As in list_tree_entries, prepend ./ to avoid interpreting leading
            # colons in pathspecs.
            picks = ["./" + pick for pick in picks]
            await self.git('add', '--force', '--', *picks)
        else:
            await self.git('add', '--all', '--force')

    async def drop_paths_from_index(self, paths):
        if not paths:
            return
        # As in list_tree_entries, prepend ./ to avoid interpreting leading
        # colons in pathspecs.
        paths = ["./" + path for path in paths]
        ls_output = await self.git(
            'ls-files', '--full-name', '-z', *paths, output_mode=BINARY_MODE)
        await self.git(
            'update-index', '--force-remove', '-z', '--stdin', input=ls_output)

    async def merge_tree_into_index(self, tree, prefix):
        # The --prefix argument to read-tree chokes on paths that contain dot
        # or dot-dot. Instead of './', it wants the empty string. Oblige it.
        # NOTE: This parameter must be forward-slash-separated, even on
        # Windows. os.path.normpath() is not correct here!
        prefix_path = pathlib.PurePosixPath(prefix)
        assert '..' not in prefix_path.parts
        prefix_arg = prefix_path.as_posix()
        prefix_arg = '' if prefix_arg == '.' else prefix_arg
        # Normally read-tree with --prefix wants to make sure changes don't
        # stomp on the working copy. The -i flag ignores the working copy.
        await self.git('read-tree', '-i', '--prefix', prefix_arg, tree)

    async def working_copy_matches_index(self):
        diff_output = await self.git('diff-files', output_mode=BINARY_MODE)
        return len(diff_output) == 0

    async def get_modified_files_skipping_deletes(self):
        # We want to ignore deleted files, so we exclude only deletes using
        # 'd' instead of including all of the capital letter forms.
        # https://git-scm.com/docs/git-diff#Documentation/git-diff.txt---diff-filterACDMRTUXB82308203
        diff_output = await self.git('diff-files', '-z', '--name-only',
                                     '--diff-filter=d')
        return [name for name in diff_output.split('\x00') if name]

    async def get_new_files_in_tree(self, previous_tree, new_tree):
        added_files_output = await self.git('diff-tree', '--diff-filter=A',
                                            '--name-only', '-r', '-z',
                                            previous_tree, new_tree)
        return added_files_output.split('\x00')

    async def read_tree_updating_working_copy(self, tree, force):
        '''This method relies on the current working copy being clean with
        respect to the current index. The benefit of this over
        checkout_missing_files_from_index(), is that is clean up files that get
        deleted between the current tree and the new one. Without force, this
        raises an error rather than overwriting modified files.'''
        if force:
            await self.git('read-tree', '--reset', '-u', tree)
        else:
            await self.git('read-tree', '-m', '-u', tree)

    async def checkout_files_from_index(self):
        # This recreates any deleted files. As far as I can tell,
        # checkout-index has no equivalent of the --full-tree flag we use with
        # ls-tree below. Instead, the --all flag seems to respect the directory
        # from which it's invoked, and only check out files below that
        # directory. This, this is currently the only command we invoke with an
        # explicit cwd. Original bug report:
        # https://github.com/buildinspace/peru/issues/210
        await self.git('checkout-index', '--all', cwd=self.working_copy)

    async def get_info_for_path(self, tree, path):
        # --full-tree makes ls-tree ignore the cwd. As in list_tree_entries,
        # prepend ./ to avoid interpreting leading colons in pathspecs.
        ls_output = await self.git('ls-tree', '--full-tree', '-z', tree,
                                   "./" + path)
        ls_lines = ls_output.strip('\x00').split('\x00')
        # Remove empty lines.
        ls_lines = list(filter(None, ls_lines))
        if len(ls_lines) == 0:
            raise FileNotFoundError('Path "{}" not found in tree {}.'.format(
                path, tree))
        assert len(ls_lines) == 1
        mode, type, sha1, name = ls_lines[0].split()
        return mode, type, sha1, name

    async def read_bytes_from_file_hash(self, sha1):
        return (await self.git(
            'cat-file', '-p', sha1, output_mode=BINARY_MODE))

    async def list_tree_entries(self, tree, path, recursive):
        # Lines in ls-tree are of the following form (note that the wide space
        # is a tab):
        # 100644 blob a2b67564ae3a7cb3237ee0ef1b7d26d70f2c213f    README.md
        entry_regex = r'(\w+) (\w+) (\w+)\t(.*)'
        command = ['ls-tree', '-z', tree]
        if path is not None:
            # If we do something like `git ls-tree -r -t HEAD foo/bar`, git
            # will include foo in the output, because it was traversed. We
            # filter those entries out below, by excluding results that are
            # shorter than the original path. However, git will canonicalize
            # paths in its output, and we need to match that behavior for the
            # comparison to work.
            canonical_path = str(pathlib.PurePosixPath(path))
            # However, another complication: ls-tree arguments are what git
            # calls "pathspecs". That means that leading colons have a special
            # meaning. In order to support leading colons, we always prefix the
            # path with dot-slash in git's arguments. As noted above, the
            # dot-slash will be stripped again in the final output.
            command += ["./" + canonical_path]
        if recursive:
            # -t means tree entries are included in the listing.
            command += ['-r', '-t']
        output = await self.git(*command)
        if not output:
            return {}
        entries = {}
        for line in output.strip('\x00').split('\x00'):
            mode, type, hash, name = re.match(entry_regex, line).groups()
            if (recursive and path is not None
                    and len(name) < len(canonical_path) and type == TREE_TYPE):
                # In recursive mode, leave out the parents of the target dir.
                continue
            entries[name] = TreeEntry(mode, type, hash)
        return entries

    async def make_tree_from_entries(self, entries):
        entry_format = '{} {} {}\t{}'
        input = '\x00'.join(
            entry_format.format(mode, type, hash, name)
            for name, (mode, type, hash) in entries.items())
        tree = await self.git('mktree', '-z', input=input)
        return tree


async def Cache(root):
    'This is the async constructor for the _Cache class.'
    cache = _Cache(root)
    await cache._init_trees()
    return cache


class _Cache:
    def __init__(self, root):
        "Don't instantiate this class directly. Use the Cache() constructor."
        self.root = root
        self.plugins_root = os.path.join(root, "plugins")
        makedirs(self.plugins_root)
        self.tmp_path = os.path.join(root, "tmp")
        makedirs(self.tmp_path)
        self.keyval = KeyVal(os.path.join(root, 'keyval'), self.tmp_path)
        self.trees_path = os.path.join(root, "trees")
        self._empty_tree = None

    async def _init_trees(self):
        if not os.path.exists(os.path.join(self.trees_path, 'HEAD')):
            makedirs(self.trees_path)
            with self.clean_git_session() as session:
                await session.init_git_dir()
            # Override any .gitattributes files that might be in the sync dir,
            # by writing 'info/attributes' in the bare repo. There are many
            # attributes that we might want to disable, but disabling 'text'
            # seems to take care of both 'text' and 'eol', which are the two
            # that I know can cause problems. We might need to add more
            # attributes here in the future. Note that other config files are
            # disabled in _git_env below.
            attributes_path = os.path.join(self.trees_path, 'info',
                                           'attributes')
            with open(attributes_path, 'w') as attributes:
                # Disable the 'text' attribute for all files.
                attributes.write('* -text')

    @contextlib.contextmanager
    def clean_git_session(self, working_copy=None):
        with self.keyval.tmp_dir_context() as tmp_dir:
            # Git will initialize a nonexistent index file. Empty files cause
            # an error though.
            index_file = os.path.join(tmp_dir, "index")
            yield GitSession(self.trees_path, index_file, working_copy)

    def no_index_git_session(self):
        return GitSession(self.trees_path, os.devnull, os.devnull)

    async def get_empty_tree(self):
        if not self._empty_tree:
            with self.clean_git_session() as session:
                self._empty_tree = await session.make_tree_from_index()
        return self._empty_tree

    async def import_tree(self, src, *, picks=None, excludes=None):
        if not os.path.exists(src):
            raise RuntimeError('import tree called on nonexistent path ' + src)
        with self.clean_git_session(src) as session:
            await session.read_working_copy_into_index(picks)

            # We want to avoid ever importing a .peru directory. This is a
            # security/correctness issue similar to git's issue with .git dirs,
            # and just like git we need to watch out for case-insensitive
            # filesystems. See also:
            # https://github.com/blog/1938-vulnerability-announced-update-your-git-clients.
            full_excludes = dotperu_exclude_case_insensitive_git_globs()
            if excludes:
                full_excludes += excludes
            await session.drop_paths_from_index(full_excludes)

            tree = await session.make_tree_from_index()
            return tree

    async def merge_trees(self, base_tree, merge_tree, merge_path='.'):
        with self.clean_git_session() as session:
            if base_tree:
                await session.read_tree_into_index(base_tree)
            try:
                await session.merge_tree_into_index(merge_tree, merge_path)
            except GitError as e:
                raise MergeConflictError(e.stdout) from e
            unified_tree = await session.make_tree_from_index()
            return unified_tree

    async def export_tree(self,
                          tree,
                          dest,
                          previous_tree=None,
                          *,
                          force=False,
                          previous_index_file=None):
        '''This method is the core of `peru sync`. If the contents of "dest"
        match "previous_tree", then export_tree() updates them to match "tree".
        If not, it raises an error and doesn't touch any files.

        Because it's important for the no-op `peru sync` to be fast, we make an
        extra optimization for this case. The caller passes in the path to the
        index file used during the last sync, which should already reflect
        "previous_tree". That allows us to skip the read-tree and update-index
        calls, so all we have to do is a single diff-files operation to check
        for cleanliness.

        It's difficult to predict all the different states the index file might
        end up in under different error conditions, not only now but also in
        past and future git versions. For safety and simplicity, if any
        operation returns an error code, we delete the supplied index file.
        Right now this includes expected errors, like "sync would overwrite
        existing files," and unexpected errors, like "index is on fire."'''

        tree = tree or (await self.get_empty_tree())
        previous_tree = previous_tree or (await self.get_empty_tree())

        makedirs(dest)

        with contextlib.ExitStack() as stack:

            # If the caller gave us an index file, create a git session around
            # it. Otherwise, create a clean one. Note that because we delete
            # the index file whenever there are errors, we also allow the
            # caller to pass in a path to a nonexistent file. In that case we
            # have to pay the cost to recreate it.
            did_refresh = False
            if previous_index_file:
                session = GitSession(self.trees_path, previous_index_file,
                                     dest)
                stack.enter_context(delete_if_error(previous_index_file))
                if not os.path.exists(previous_index_file):
                    did_refresh = True
                    await session.read_tree_and_stats_into_index(previous_tree)
            else:
                session = stack.enter_context(self.clean_git_session(dest))
                did_refresh = True
                await session.read_tree_and_stats_into_index(previous_tree)

            # The fast path. If the previous tree is the same as the current
            # one, and no files have changed at all, short-circuit.
            if previous_tree == tree:
                if (await session.working_copy_matches_index()):
                    return

            # Everything below is the slow path. Some files have changed, or
            # the tree has changed, or both. If we didn't refresh the index
            # file above, we must do so now.
            if not did_refresh:
                await session.read_tree_and_stats_into_index(previous_tree)
            modified = await session.get_modified_files_skipping_deletes()
            if modified and not force:
                raise DirtyWorkingCopyError(
                    'Imported files have been modified ' +
                    '(use --force to overwrite):\n\n' +
                    _format_file_lines(modified))

            # Do all the file updates and deletions needed to produce `tree`.
            try:
                await session.read_tree_updating_working_copy(tree, force)
            except GitError:
                # Give a more informative error if we failed because files that
                # are new in `tree` already existed in the working copy.
                new_files = await session.get_new_files_in_tree(
                    previous_tree, tree)
                existing_new_files = [
                    f for f in new_files
                    if f and os.path.exists(os.path.join(dest, f))
                ]
                existing_new_files.sort()
                if existing_new_files:
                    raise DirtyWorkingCopyError(
                        'Imports would overwrite preexisting files '
                        '(use --force to write anyway):\n\n' +
                        _format_file_lines(existing_new_files))
                else:
                    # We must've failed for some other reason. Let the error
                    # keep going.
                    raise

            # Recreate any missing files.
            await session.checkout_files_from_index()

    async def read_file(self, tree, path):
        # TODO: Make this handle symlinks in the tree.
        with self.clean_git_session() as session:
            mode, type, sha1, name = await session.get_info_for_path(
                tree, path)
            if type == 'tree':
                raise IsADirectoryError(
                    'Path "{}" in tree {} is a directory.'.format(path, tree))
            assert type == 'blob'
            return (await session.read_bytes_from_file_hash(sha1))

    async def ls_tree(self, tree, path=None, *, recursive=False):
        session = self.no_index_git_session()
        return (await session.list_tree_entries(tree, path, recursive))

    async def modify_tree(self, tree, modifications):
        '''The modifications are a map of the form, {path: TreeEntry}. The tree
        can be None to indicate an empty starting tree. The entries can be
        either blobs or trees, or None to indicate a deletion. The return value
        is either the hash of the resulting tree, or None if the resulting tree
        is empty. Modifications in parent directories are done before
        modifications in subdirectories below them, so for example you can
        insert a tree at a given path and also insert more new stuff beneath
        that path, without fear of overwriting the new stuff.'''

        # Read the original contents of the base tree.
        if tree is None:
            entries = {}
        else:
            entries = await self.ls_tree(tree, '.')

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
        empty_tree = (await self.get_empty_tree())
        for name, sub_modifications in modifications_in_subtrees.items():
            subtree_base = None
            if name in entries and entries[name].type == TREE_TYPE:
                subtree_base = entries[name].hash
            new_subtree = await self.modify_tree(subtree_base,
                                                 sub_modifications)
            if new_subtree != empty_tree:
                entries[name] = TreeEntry(TREE_MODE, TREE_TYPE, new_subtree)
            # Delete an empty tree if it was actually a tree to begin with.
            elif name in entries and entries[name].type == TREE_TYPE:
                del entries[name]

        # Return the resulting tree, or None if empty.
        if entries:
            session = self.no_index_git_session()
            tree = await session.make_tree_from_entries(entries)
            return tree
        else:
            return empty_tree


@contextlib.contextmanager
def delete_if_error(path):
    '''If any exception is raised inside the context, delete the file at the
    given path, and allow the exception to continue.'''
    try:
        yield
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


def _format_file_lines(files):
    '''Given a list of filenames that we're about to print, limit it to a
    reasonable number of lines.'''
    LINES_TO_SHOW = 10
    if len(files) <= LINES_TO_SHOW:
        lines = '\n'.join(files)
    else:
        lines = ('\n'.join(files[:LINES_TO_SHOW - 1]) + '\n...{} total'.format(
            len(files)))
    return lines


class GitError(Exception):
    def __init__(self, command, errorcode, stdout, stderr):
        self.command = " ".join(command)
        self.errorcode = errorcode
        self.stdout = stdout
        self.stderr = stderr
        message = textwrap.dedent('''\
            git command "{}" returned error code {}.
            stdout: {}
            stderr: {}''').format(command, errorcode, stdout, stderr)
        Exception.__init__(self, message)


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

# All possible ways to capitalize ".peru", to exclude from imported trees.
DOTPERU_CAPITALIZATIONS = [
    '.peru',
    '.Peru',
    '.pEru',
    '.peRu',
    '.perU',
    '.PEru',
    '.PeRu',
    '.PerU',
    '.pERu',
    '.pErU',
    '.peRU',
    '.PERu',
    '.PErU',
    '.PeRU',
    '.pERU',
    '.PERU',
]


def dotperu_exclude_case_insensitive_git_globs():
    """These use the glob syntax accepted by `git ls-files` (NOT our own
    glob.py). Note that ** must match at least one path component, so we have
    to use separate globs for matches at the root and matches below."""
    globs = []
    for capitalization in DOTPERU_CAPITALIZATIONS:
        globs.append(capitalization + '/**')
        globs.append('**/' + capitalization + '/**')
    return globs

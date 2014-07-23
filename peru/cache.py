import hashlib
import json
import os
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
        self._init_trees()

    def _init_trees(self):
        if os.path.exists(self.trees_path):
            return
        os.makedirs(self.trees_path)
        self._git("init", "--bare")
        self._git("config", "user.name", "peru")
        self._git("config", "user.email", "peru")

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

    def _git(self, *args, work_tree=None, input=None):
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
            universal_newlines=True)
        output, _ = process.communicate(input=input)
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

    def save_tree(self, tree, name, message=None):
        if message is None:
            message = name
        try:
            # throws if branch doesn't exist
            self._git("show-ref", "--verify", "--quiet", "refs/heads/" + name)
        except self.GitError:
            # branch doesn't exist, create an orphan commit
            commit = self._git("commit-tree", "-m", message, tree)
        else:
            # branch does exist, use it as the parent
            parent = self._git("rev-parse", name)
            commit = self._git("commit-tree", "-m", message, "-p", parent,
                               tree)
        self._git("branch", "-f", name, commit)

    def import_tree(self, src, files=None):
        if not os.path.exists(src):
            raise RuntimeError('import tree called on nonexistent path ' + src)
        self._git('read-tree', '--empty')  # clear the index for safety
        # Use --force to avoid .gitignore rules. We shouldn't respect them.
        if files:
            self._git('add', '--force', '--', *files, work_tree=src)
        else:
            self._git('add', '--all', '--force', work_tree=src)
        tree = self._git('write-tree')
        return tree

    def merge_trees(self, base_tree, merge_tree, merge_path):
        if base_tree:
            self._git("read-tree", base_tree)
        else:
            self._git("read-tree", "--empty")

        # The --prefix argument to read-tree chokes on paths that contain dot
        # or dot-dot. Instead of "./", it wants the empty string. Oblige it.
        # TODO: This could change the meaning of .. with respect to symlinks.
        #       Should we ban .. entirely in import paths?
        prefix = os.path.normpath(merge_path)
        prefix = "" if prefix == "." else prefix

        # The git docs say that a --prefix value must end in a slash. That
        # doesn't seem to be true in practice, but better safe than sorry. Note
        # that git treats "--prefix=/" as the root of the tree, so this doesn't
        # break that case.
        if not prefix.endswith("/"):
            prefix += "/"

        # Normally read-tree with --prefix wants to make sure changes don't
        # stomp on the working copy. The -i flag tells it to pretend the
        # working copy doesn't exist. (Which is important, because we don't
        # have one right now!)
        try:
            self._git("read-tree", "-i", "--prefix", prefix, merge_tree)
        except self.GitError as e:
            raise MergeConflictError(e.output) from e

        unified_tree = self._git("write-tree")
        return unified_tree

    def _dummy_commit(self, tree):
        if tree is None:
            self._git("read-tree", "--empty")
            tree = self._git("write-tree")
        self._git("read-tree", tree)
        return self._git("commit-tree", "-m", "<dummy>", tree)

    def _checkout_dummy_commit(self, tree):
        dummy = self._dummy_commit(tree)  # includes a call to read-tree
        self._git("update-ref", "--no-deref", "HEAD", dummy)
        return dummy

    # TODO: This method needs to take a filesystem lock.  Probably all of them
    # do.
    def export_tree(self, tree, dest, previous_tree=None, *, force=False):
        if not os.path.exists(dest):
            os.makedirs(dest)

        next_commit = self._dummy_commit(tree)
        self._checkout_dummy_commit(previous_tree)

        # Checking git status serves two purposes here.
        # 1) It checks for a dirty working copy, in which case we'll abort.
        # 2) It updates file timestamps in the index. (Yes, Virginia,
        # `git status` writes to the index file!) This solves a very subtle
        # issue where `git reset --keep` mistakenly thinks a file is dirty when
        # in fact only the timestamp is off. The timestamp is off because
        # `git read-tree` can't set timestamps (git trees don't store them).
        status = self._git("status", "--porcelain", "--untracked-files=no",
                           work_tree=dest)
        if status and not force:
            # Working copy is dirty. Abort.
            raise DirtyWorkingCopyError(status)

        # Use `git reset` to update the working copy instead of `git checkout`.
        # The checkout command normally refuses to overwrite existing files,
        # which is good, but it will gladly overwrite ignored files. In our
        # case, we don't control any .gitignore files that might be in the
        # working copy. (In fact, it's expected that users will gitignore the
        # files that peru syncs.) Without the --force flag, we should never
        # overwrite any dirty files, ignored or otherwise. Luckily, `git reset`
        # doesn't pay attention to .gitignore.
        reset_mode = "--hard" if force else "--keep"
        try:
            self._git("reset", reset_mode, next_commit, work_tree=dest)
        except self.GitError as e:
            raise DirtyWorkingCopyError(e.output) from e


class DirtyWorkingCopyError(PrintableError):
    pass


class MergeConflictError(PrintableError):
    pass

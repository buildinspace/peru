import collections
import hashlib
import json
import os
import shutil
import subprocess
import tempfile


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
        self.tmp_path = os.path.join(root, "tmp")
        os.makedirs(self.tmp_path, exist_ok=True)
        self.keyval = KeyVal(self)
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
        output = output.strip()
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

    def _save_tree_to_branch(self, tree, name, message=None):
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

    def import_tree(self, src, name):
        # We're going to return a tree hash to the caller, but we want a real
        # commit representing that tree to be stored in a real branch. That's
        # both because we don't want this tree to get garbage-collected, and
        # because it's nicer for debugging to be able to see the output of your
        # rules.
        self._git("read-tree", "--empty")  # clear the index for safety
        self._git("add", "--all", work_tree=src)
        tree = self._git("write-tree")
        self._save_tree_to_branch(tree, name)
        return tree

    def _dummy_commit(self, tree):
        if tree is None:
            self._git("read-tree", "--empty")
            tree = self._git("write-tree")
        self._git("read-tree", tree)
        return self._git("commit-tree", "-m", "<dummy>", tree)

    # TODO: This method needs to take a filesystem lock.  Probably all of them
    # do.
    def export_tree(self, tree, dest, previous_tree=None):
        # We want to use git-checkout semantics, and for that we need commits
        # instead of trees.
        previous_commit = self._dummy_commit(previous_tree)
        next_commit = self._dummy_commit(tree)

        self._git("update-ref", "--no-deref", "HEAD", previous_commit)
        self._git("read-tree", "HEAD")

        if not os.path.exists(dest):
            os.makedirs(dest)

        # TODO: Stop using --force. Instead, unify all imports into a single
        # tree, so that we can do real cleanup.
        self._git("checkout", "--force", next_commit, work_tree=dest)

    def _resolve_hash(self, rev):
        return self._git("rev-parse", rev)

    # TODO: Have tmp_file and tmp_dir return a nice context manager.
    def tmp_file(self):
        fd, path = tempfile.mkstemp(dir=self.tmp_path)
        os.close(fd)
        os.chmod(path, 0o644)  # See comment in tmp_dir().
        return path

    def tmp_dir(self):
        # Restrictive permissions are a security measure for temp files created
        # in a shared location like /tmp. Our temp directory is under
        # .peru-cache/, so we don't need to be extra restrictive. Also weird
        # permissions confuse utilities like os.makedirs(exist_ok=True).
        path = tempfile.mkdtemp(dir=self.tmp_path)
        os.chmod(path, 0o755)
        return path


class KeyVal:
    def __init__(self, cache):
        self.cache = cache
        self.keyval_root = os.path.join(cache.root, "keyval")
        os.makedirs(self.keyval_root, exist_ok=True)

    def __getitem__(self, key):
        with open(self.key_path(key)) as f:
            return f.read()

    def __setitem__(self, key, val):
        # Write to a tmp file first, to avoid partial reads.
        tmp_path = self.cache.tmp_file()
        with open(tmp_path, "w") as f:
            f.write(val)
        shutil.move(tmp_path, self.key_path(key))

    def __contains__(self, key):
        return os.path.isfile(self.key_path(key))

    def key_path(self, key):
        return os.path.join(self.keyval_root, key)


TreeStatus = collections.namedtuple(
    "TreeStatus",
    ["present", "added", "deleted", "modified"])

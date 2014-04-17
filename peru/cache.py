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
        os.makedirs(self.trees_path, exist_ok=True)
        self._git("init", "--bare")
        # TODO: Disable automatic gc somehow?

    class GitError(RuntimeError):
        pass

    def _git(self, *args, work_tree=None, input=None):
        command = ["git"]
        command.append("--git-dir=" + self.trees_path)
        if work_tree:
            command.append("--work-tree=" + work_tree)
        command.extend(args)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True)
        output, _ = process.communicate(input=input)
        if process.returncode != 0:
            raise self.GitError(
                'git command "{}" returned error code {}:\n{}'.format(
                    " ".join(command),
                    process.returncode,
                    output))
        return output

    def import_tree(self, src, name, blob=None):
        try:
            # throw if branch doesn't exist
            self._git("show-ref", "--verify", "--quiet", "refs/heads/" + name)
        except self.GitError:
            # branch doesn't exist, create it
            self._git("checkout", "--orphan", name, work_tree=src)
        else:
            # branch does exist, do the equivalent of checkout for a bare repo
            self._git("symbolic-ref", "HEAD", "refs/heads/" + name)
        self._git("add", "--all", work_tree=src)
        commit_message = name + ("\n\n" + blob if blob else "")
        self._git("commit", "--allow-empty", "--message", commit_message,
                  work_tree=src)
        hash_ = self._git("write-tree")
        return hash_.strip()

    # TODO: This method needs to take a filesystem lock.  Probably all of them
    # do.
    def export_tree(self, hash_, dest):
        self._git("read-tree", hash_)
        os.makedirs(dest, exist_ok=True)
        self._git("checkout-index", "--all", work_tree=dest)

    def tree_status(self, hash_, dest):
        self._git("read-tree", hash_)
        # TODO: Test this with weird file names, like with newlines.
        out = self._git("status", "--porcelain", "-z", work_tree=dest)
        present = set()
        added = set()
        deleted = set()
        modified = set()
        for line in out.strip("\0").split("\0"):
            status = line[:2]
            file_ = line[3:]
            if status == "A ":
                present.add(file_)
            elif status == "??":
                added.add(file_)
            elif status == "AD":
                deleted.add(file_)
            elif status == "AM":
                modified.add(file_)
            else:
                raise RuntimeError("Unknown git status: " + status)
        return TreeStatus(present, added, deleted, modified)

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

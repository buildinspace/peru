import collections
import hashlib
import json
import os
import subprocess

def compute_key(data):
    # To hash this dictionary of fields, serialize it as a JSON string, and
    # take the SHA1 of that string. Dictionary key order is unspecified, so
    # "sort_keys" keeps our hash stable. Specifying separators makes the
    # JSON slightly more compact, and protects us against changes in the
    # default.  "ensure_ascii" defaults to true, so specifying it just
    # protects us from changes in the default.
    json_representation = json.dumps(data, sort_keys=True,
                                     ensure_ascii=True,
                                     separators=(',', ':'))
    sha1 = hashlib.sha1()
    sha1.update(json_representation.encode("utf8"))
    return sha1.hexdigest()

class Cache:
    def __init__(self, root):
        self.root = root
        self.trees_path = os.path.join(root, "trees")
        os.makedirs(self.trees_path, exist_ok=True)
        self._git("init", "--bare")
        # TODO: Disable automatic gc somehow.

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

    def put_tree(self, src, name, blob=None):
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
        commit_message = name
        if blob:
            commit_message += "\n\n" + blob
        self._git("commit", "--message", commit_message, work_tree=src)
        hash_ = self._git("write-tree")
        return hash_.strip()

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

TreeStatus = collections.namedtuple(
    "TreeStatus",
    ["present", "added", "deleted", "modified"])

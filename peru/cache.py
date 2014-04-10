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

    def _git(self, *args, work_tree=None):
        command = ["git"]
        command.append("--git-dir=" + self.trees_path)
        if work_tree:
            command.append("--work-tree=" + work_tree)
        command.extend(args)
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True)
        output, _ = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                "git exited with error code {0}:\n$ {1}\n{2}".format(
                    process.returncode, " ".join(command), output))
        return output

    def put_tree(self, src):
        self._git("read-tree", "--empty")
        self._git("add", "-A", work_tree=src)
        hash_ = self._git("write-tree")
        return hash_

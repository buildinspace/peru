import distutils.dir_util
import hashlib
import json
import os
import shutil

def compute_key(obj):
    # To hash this dictionary of fields, serialize it as a JSON string, and
    # take the SHA1 of that string. Dictionary key order is unspecified, so
    # "sort_keys" keeps our hash stable. Specifying separators makes the
    # JSON slightly more compact, and protects us against changes in the
    # default.  "ensure_ascii" defaults to true, so specifying it just
    # protects us from changes in the default.
    json_representation = json.dumps(obj, sort_keys=True,
                                     ensure_ascii=True,
                                     separators=(',', ':'))
    sha1 = hashlib.sha1()
    sha1.update(json_representation.encode("utf8"))
    return sha1.hexdigest()

class Cache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _cache_path(self, cache_key):
        return os.path.join(self.root, "cache", cache_key)

    def has(self, cache_key):
        return os.path.isdir(self._cache_path(cache_key))

    def put(self, cache_key, src_dir):
        if self.has(cache_key):
            shutil.rmtree(self._cache_path(cache_key))
        os.makedirs(self._cache_path(cache_key))
        distutils.dir_util.copy_tree(src_dir, self._cache_path(cache_key),
                                     preserve_symlinks=True)

    def get(self, cache_key, dest_dir):
        src_dir = self._cache_path(cache_key)
        distutils.dir_util.copy_tree(src_dir, dest_dir, preserve_symlinks=True)

import distutils.dir_util
import os
import shutil

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

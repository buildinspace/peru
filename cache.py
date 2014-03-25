import distutils
import os

def cache_root():
    return os.getenv("PERU_CACHE_NAME") or ".peru-cache"

def cached_files_path(cache_key):
    return os.path.join(cache_root(), "cache", cache_key)

def has_cached_files(cache_key):
    return os.path.isdir(cached_files_path(cache_key))

def save_files_to_cache(cache_key, path):
    distutils.dir_util.copy_tree(src, cached_files_path(cache_key),
                                preserve_symlinks=True)


def retrieve_files_from_cache(cache_key, dest):
    src = cached_files_path(cache_key)
    distutils.dir_util.copy_tree(src, dest, preserve_symlinks=True)

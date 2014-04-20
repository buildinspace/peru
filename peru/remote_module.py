import shutil

from .cache import compute_key


class RemoteModule:
    def __init__(self, name, imports, plugin, plugin_fields):
        self.name = name
        self.imports = imports
        self.plugin = plugin
        self.plugin_fields = plugin_fields

    def cache_key(self):
        digest = compute_key({
            # TODO: Get imports in here
            "plugin": self.plugin.name,
            "plugin_fields": self.plugin_fields,
        })
        return digest

    # TODO: Imports should be included before this tree hits the cache.
    def get_tree(self, cache):
        key = self.cache_key()
        if key in cache.keyval:
            # tree is already in cache
            return cache.keyval[key]
        tmp_dir = cache.tmp_dir()
        try:
            self.plugin.get_files_callback(
                self.plugin_fields, tmp_dir, self.name)
            tree = cache.import_tree(tmp_dir, self.name)
        finally:
            shutil.rmtree(tmp_dir)
        cache.keyval[key] = tree
        return tree

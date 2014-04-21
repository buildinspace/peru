import shutil

from .cache import compute_key


class RemoteModule:
    def __init__(self, name, imports, plugin, plugin_fields):
        self.name = name
        self.imports = imports
        self.plugin = plugin
        self.plugin_fields = plugin_fields

    def cache_key(self, resolver):
        # TODO: This logic is duplicated in Rule.
        trees = resolver.resolve_trees(self.imports.keys())
        import_trees = {trees[target]: path
                        for target, path in self.imports.items()}
        digest = compute_key({
            "import_trees": import_trees,
            "plugin": self.plugin.name,
            "plugin_fields": self.plugin_fields,
        })
        return digest

    def get_tree(self, cache, resolver):
        key = self.cache_key(resolver)
        if key in cache.keyval:
            # tree is already in cache
            return cache.keyval[key]
        tmp_dir = cache.tmp_dir()
        try:
            self.plugin.get_files_callback(
                self.plugin_fields, tmp_dir, self.name)
            resolver.apply_imports(self.imports, tmp_dir)
            tree = cache.import_tree(tmp_dir, self.name)
        finally:
            shutil.rmtree(tmp_dir)
        cache.keyval[key] = tree
        return tree

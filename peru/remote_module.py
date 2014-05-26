from .cache import compute_key
from .plugin import plugin_fetch


class RemoteModule:
    def __init__(self, name, type, imports, default_rule, plugin_fields,
                 yaml_name):
        self.name = name
        self.type = type
        self.imports = imports
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        self.yaml_name = yaml_name  # used by reup to edit the markup

    def cache_key(self, resolver):
        # NB: Resolving imports builds them if they haven't been built before.
        import_treepaths = resolver.resolve_imports_to_treepaths(self.imports)
        import_trees = [(tree, path) for tree, path, _ in import_treepaths]
        digest = compute_key({
            "import_trees": import_trees,
            "type": self.type,
            "plugin_fields": self.plugin_fields,
        })
        return digest

    def get_tree(self, cache, resolver):
        key = self.cache_key(resolver)
        if key in cache.keyval:
            # tree is already in cache
            return cache.keyval[key]
        with cache.tmp_dir() as tmp_dir:
            plugin_fetch(cache.plugins_root, self.type, tmp_dir,
                         self.plugin_fields)
            resolver.apply_imports(self.imports, tmp_dir)
            tree = cache.import_tree(tmp_dir)
        cache.keyval[key] = tree
        return tree

    def reup(self, peru_file_name):
        print("reupping", self.name, '("{}")'.format(self.yaml_name))

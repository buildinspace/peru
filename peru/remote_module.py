from .cache import compute_key
from .edit_yaml import set_module_field_in_file
from .merge import merge_imports_tree
from .local_module import LocalModule
from .plugin import plugin_fetch, plugin_get_reup_fields
from . import resolver


class RemoteModule:
    def __init__(self, name, type, imports, default_rule, plugin_fields,
                 yaml_name):
        self.name = name
        self.type = type
        self.imports = imports
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        self.yaml_name = yaml_name  # used by reup to edit the markup

    def get_tree(self, runtime):
        # These two will eventually be done in parallel.
        fetch_tree = self._get_fetch_tree(runtime)
        target_trees = resolver.get_trees(runtime, self.imports.targets)
        return merge_imports_tree(
            runtime.cache, self.imports, target_trees, fetch_tree)

    def _get_fetch_tree(self, runtime):
        key = compute_key({
            "type": self.type,
            "plugin_fields": self.plugin_fields,
        })
        if key in runtime.cache.keyval:
            return runtime.cache.keyval[key]
        with runtime.tmp_dir() as tmp_dir:
            plugin_fetch(runtime.root, runtime.cache.plugins_root,
                         tmp_dir, self.type, self.plugin_fields,
                         plugin_roots=runtime.plugin_roots)
            tree = runtime.cache.import_tree(tmp_dir)
        runtime.cache.keyval[key] = tree
        return tree

    def reup(self, runtime):
        if not runtime.quiet:
            print("reup", self.name)
        reup_fields = plugin_get_reup_fields(
            runtime.root, runtime.cache.plugins_root, self.type,
            self.plugin_fields, plugin_roots=runtime.plugin_roots)
        for field, val in reup_fields.items():
            if (field not in self.plugin_fields or
                    val != self.plugin_fields[field]):
                if not runtime.quiet:
                    print("  {}: {}".format(field, val))
                set_module_field_in_file(
                    runtime.peru_file, self.yaml_name, field, val)

    def get_local_override(self, path):
        return LocalModule(self.imports, self.default_rule, path)

import asyncio

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

    @asyncio.coroutine
    def get_tree(self, runtime):
        # Fetch this module and its dependencies in parallel.
        fetch_tree, target_trees = yield from asyncio.gather(
            self._get_fetch_tree(runtime),
            resolver.get_trees(runtime, self.imports.targets))
        return merge_imports_tree(
            runtime.cache, self.imports, target_trees, fetch_tree)

    @asyncio.coroutine
    def _get_fetch_tree(self, runtime):
        key = compute_key({
            "type": self.type,
            "plugin_fields": self.plugin_fields,
        })
        # Use a lock to prevent the same module from being double fetched. The
        # lock is taken on the cache key, not the module itself, so two
        # different modules with identical fields will take the same lock and
        # avoid double fetching.
        cache_key_lock = runtime.module_cache_locks[key]
        with (yield from cache_key_lock):
            if key in runtime.cache.keyval:
                return runtime.cache.keyval[key]
            with runtime.tmp_dir() as tmp_dir:
                yield from plugin_fetch(
                    runtime.get_plugin_context(), self.type,
                    self.plugin_fields, tmp_dir)
                tree = runtime.cache.import_tree(tmp_dir)
        runtime.cache.keyval[key] = tree
        return tree

    @asyncio.coroutine
    def reup(self, runtime):
        reup_fields = yield from plugin_get_reup_fields(
            runtime.get_plugin_context(), self.type, self.plugin_fields)
        if not runtime.quiet:
            print('reup', self.name)
        for field, val in reup_fields.items():
            if (field not in self.plugin_fields or
                    val != self.plugin_fields[field]):
                if not runtime.quiet:
                    print('  {}: {}'.format(field, val))
                set_module_field_in_file(
                    runtime.peru_file, self.yaml_name, field, val)

    def get_local_override(self, path):
        return LocalModule(self.imports, self.default_rule, path)

import asyncio

from .cache import compute_key
from .edit_yaml import set_module_field_in_file
from .merge import merge_imports_tree
from .local_module import LocalModule
from .plugin import plugin_fetch, plugin_get_reup_fields
from . import resolver


DEFAULT_PARALLEL_FETCH_LIMIT = 10


class RemoteModule:
    def __init__(self, name, type, imports, default_rule, plugin_fields,
                 yaml_name):
        self.name = name
        self.type = type
        self.imports = imports
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        self.yaml_name = yaml_name  # used by reup to edit the markup
        self.module_lock = asyncio.Lock()

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
        # Use a lock to prevent the same module from being fetched more than
        # once before it makes it into cache. Use a semaphore to make sure that
        # we don't run too many fetches at once. It's important to take the
        # lock before the semaphore, so that semaphore slots aren't wasted
        # waiting on the lock.
        with (yield from self.module_lock):
            if key in runtime.cache.keyval:
                return runtime.cache.keyval[key]
            with (yield from runtime.fetch_semaphore):
                with runtime.tmp_dir() as tmp_dir:
                    yield from plugin_fetch(
                        runtime.root, runtime.cache.plugins_root, tmp_dir,
                        self.type, self.plugin_fields,
                        plugin_paths=runtime.plugin_paths)
                    tree = runtime.cache.import_tree(tmp_dir)
        runtime.cache.keyval[key] = tree
        return tree

    @asyncio.coroutine
    def reup(self, runtime):
        with (yield from runtime.fetch_semaphore):
            reup_fields = yield from plugin_get_reup_fields(
                runtime.root, runtime.cache.plugins_root, self.type,
                self.plugin_fields, plugin_paths=runtime.plugin_paths)
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

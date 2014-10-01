import asyncio

from .cache import compute_key
from .edit_yaml import set_module_field_in_file
from .local_module import LocalModule
from .plugin import plugin_fetch, plugin_get_reup_fields


class RemoteModule:
    def __init__(self, name, type, default_rule, plugin_fields, yaml_name):
        self.name = name
        self.type = type
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        self.yaml_name = yaml_name  # used by reup to edit the markup

    @asyncio.coroutine
    def get_tree(self, runtime):
        key = compute_key({
            "type": self.type,
            "plugin_fields": self.plugin_fields,
        })
        # Use a lock to prevent the same module from being double fetched. The
        # lock is taken on the cache key, not the module itself, so two
        # different modules with identical fields will take the same lock and
        # avoid double fetching.
        cache_key_lock = runtime.cache_key_locks[key]
        with (yield from cache_key_lock):
            if key in runtime.cache.keyval:
                return runtime.cache.keyval[key]
            with runtime.tmp_dir() as tmp_dir:
                yield from plugin_fetch(
                    runtime.get_plugin_context(), self.type,
                    self.plugin_fields, tmp_dir,
                    runtime.display.get_handle(self.name))
                tree = runtime.cache.import_tree(tmp_dir)
            runtime.cache.keyval[key] = tree
        return tree

    @asyncio.coroutine
    def reup(self, runtime):
        reup_fields = yield from plugin_get_reup_fields(
            runtime.get_plugin_context(), self.type, self.plugin_fields,
            runtime.display.get_handle(self.name))
        output_lines = []
        for field, val in reup_fields.items():
            if (field not in self.plugin_fields or
                    val != self.plugin_fields[field]):
                output_lines.append('  {}: {}'.format(field, val))
                set_module_field_in_file(
                    runtime.peru_file, self.yaml_name, field, val)
        if output_lines and not runtime.quiet:
            runtime.display.print('reup ' + self.name)
            for line in output_lines:
                runtime.display.print(line)

    def get_local_override(self, path):
        return LocalModule(None, self.default_rule, path)

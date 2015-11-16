import asyncio
import os

from .cache import compute_key
from .error import PrintableError
from .edit_yaml import set_module_field_in_file
from . import imports
from .plugin import plugin_fetch, plugin_get_reup_fields
from . import scope


class Module:
    def __init__(self, name, type, default_rule, plugin_fields, yaml_name,
                 peru_file):
        self.name = name
        self.type = type
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        self.yaml_name = yaml_name  # used by reup to edit the markup
        self.peru_file = peru_file  # for recursive module definitions

    @asyncio.coroutine
    def _get_base_tree(self, runtime):
        override_path = runtime.get_override(self.name)
        if override_path is not None:
            return self._get_override_tree(runtime, override_path)

        key = compute_key({
            'type': self.type,
            'plugin_fields': self.plugin_fields,
            'peru_file': self.peru_file,
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
    def get_tree(self, runtime):
        # TODO: memoize the tree or something
        base_tree = yield from self._get_base_tree(runtime)
        scope, _imports = yield from self.parse_peru_file(runtime)
        if not scope:
            return base_tree
        recursive_tree = yield from imports.get_imports_tree(
            runtime, scope, _imports, base_tree=base_tree)
        return recursive_tree

    @asyncio.coroutine
    def parse_peru_file(self, runtime):
        from . import parser  # avoid circular imports
        tree = yield from self._get_base_tree(runtime)
        try:
            yaml = runtime.cache.read_file(tree, self.peru_file)
        except FileNotFoundError:
            # This module is not a peru project.
            return (None, None)
        prefix = self.name + scope.SCOPE_SEPARATOR
        return parser.parse_string(yaml, name_prefix=prefix)

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

    def _get_override_tree(self, runtime, path):
        if not os.path.exists(path):
            raise PrintableError(
                "override path for module '{}' does not exist: {}".format(
                    self.name, path))
        if not os.path.isdir(path):
            raise PrintableError(
                "override path for module '{}' is not a directory: {}".format(
                    self.name, path))
        return runtime.cache.import_tree(path)

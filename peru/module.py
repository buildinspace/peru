import asyncio
import json
import os
import textwrap

from .cache import compute_key
from .error import PrintableError
from .edit_yaml import set_module_field_in_file
from . import imports
from .plugin import plugin_fetch, plugin_get_reup_fields
from . import scope


recursion_warning = '''\
WARNING: The peru module '{}' doesn't specify the 'recursive' field,
but its contents include a peru.yaml file. Peru's behavior here changed
in version 0.4: modules with peru.yaml files are *no longer* recursive
by default. Add 'recursive: true' to the module definition to re-enable
recursive fetching.
'''


class Module:
    def __init__(self, name, type, default_rule, plugin_fields, yaml_name,
                 peru_file, recursive):
        self.name = name
        self.type = type
        self.default_rule = default_rule
        self.plugin_fields = plugin_fields
        # used by reup to edit the markup
        self.yaml_name = yaml_name
        # for recursive module definitions
        self.peru_file = peru_file
        # whether to automatically fetch recursive imports
        self.recursive = bool(recursive)
        self.recursion_specified = recursive is not None

    @asyncio.coroutine
    def _get_base_tree(self, runtime):
        override_path = runtime.get_override(self.name)
        if override_path is not None:
            # Marking overrides as used lets us print a warning when an
            # override is unused.
            runtime.mark_override_used(self.name)
            override_tree = yield from self._get_override_tree(
                runtime, override_path)
            return override_tree

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
            # Skip reading the cache if --no-cache is set. This is the only
            # place in the code we check that flag. Deterministic operations
            # like tree merging still get read from cache, because there's no
            # reason to redo them.
            if key in runtime.cache.keyval and not runtime.no_cache:
                return runtime.cache.keyval[key]
            with runtime.tmp_dir() as tmp_dir:
                yield from plugin_fetch(
                    runtime.get_plugin_context(), self.type,
                    self.plugin_fields, tmp_dir,
                    runtime.display.get_handle(self.name))
                tree = yield from runtime.cache.import_tree(tmp_dir)
            # Note that we still *write* to cache even when --no-cache is True.
            # That way we avoid confusing results on subsequent syncs.
            runtime.cache.keyval[key] = tree
        return tree

    @asyncio.coroutine
    def get_tree(self, runtime):
        # NOTE: While the recursion warning is in place, there is a 2x3 set of
        # states we want to keep track of. On the one side, a module either
        # does or does not have a peru.yaml file. On the other side, the
        # recursion setting for that module can be true, false, or unspecified.
        # It's the possible+unspecified state that we're interested in for
        # printing the warning.
        base_tree = yield from self._get_base_tree(runtime)
        scope, _imports = yield from self.parse_peru_file(runtime)
        recursion_possible = scope is not None
        if not recursion_possible:
            return base_tree
        # TODO: Get rid of this with 1.0, and move the self.recursive check up.
        if not self.recursion_specified:
            runtime.display.print(
                '\n'.join(textwrap.wrap(recursion_warning.format(self.name))))
        if not self.recursive:
            return base_tree
        recursive_tree = yield from imports.get_imports_tree(
            runtime, scope, _imports, base_tree=base_tree)
        return recursive_tree

    @asyncio.coroutine
    def parse_peru_file(self, runtime):
        from . import parser  # avoid circular imports
        tree = yield from self._get_base_tree(runtime)
        cache_key = compute_key({
            'key_type': 'module_peru_file',
            'input_tree': tree,
            'file_name': self.peru_file,
        })
        if cache_key in runtime.cache.keyval:
            yaml = json.loads(runtime.cache.keyval[cache_key])
        else:
            try:
                yaml_bytes = yield from runtime.cache.read_file(
                    tree, self.peru_file)
                yaml = yaml_bytes.decode('utf8')
            except FileNotFoundError:
                yaml = None
            runtime.cache.keyval[cache_key] = json.dumps(yaml)
        if yaml is None:
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

    @asyncio.coroutine
    def _get_override_tree(self, runtime, path):
        if not os.path.exists(path):
            raise PrintableError(
                "override path for module '{}' does not exist: {}".format(
                    self.name, path))
        if not os.path.isdir(path):
            raise PrintableError(
                "override path for module '{}' is not a directory: {}".format(
                    self.name, path))
        tree = yield from runtime.cache.import_tree(path)
        return tree

import asyncio
import os

from . import compat
from .merge import merge_imports_tree
from . import resolver


class LocalModule:
    def __init__(self, imports, default_rule, root='.', peru_dir=None):
        self.imports = imports
        self.default_rule = default_rule
        self.root = root

        # The toplevel module might relocate its own .peru directory with the
        # PERU_DIR variable. Overridden remote modules will just use the
        # default.
        # NOTE: You can get into a confusing situation if you use a nonstandard
        # .peru dir in your project, and then also use your project as a local
        # override for a *different* project. The two different perus won't be
        # talking to the same lastimports file, and your imports may get dirty.
        # This is a tiny corner case, but maybe we should try to detect it?
        # TODO: LocalModule should probably be renamed to OverrideModule and
        # should no longer modify the override dir at all. See
        # https://github.com/buildinspace/peru/issues/72.
        self.peru_dir = peru_dir or os.path.join(root, ".peru")

    @asyncio.coroutine
    def apply_imports(self, runtime, custom_imports=None):
        imports = custom_imports or self.imports
        if imports is None:
            return

        target_trees = yield from resolver.get_trees(runtime, imports.targets)
        imports_tree = merge_imports_tree(runtime.cache, imports, target_trees)

        last_imports_tree = self._get_last_imports()
        runtime.cache.export_tree(imports_tree, self.root, last_imports_tree,
                                  force=runtime.force)
        self._set_last_imports(imports_tree)

    def _last_imports_path(self):
        return os.path.join(self.peru_dir, 'lastimports')

    def _get_last_imports(self):
        last_imports_tree = None
        if os.path.exists(self._last_imports_path()):
            with open(self._last_imports_path()) as f:
                last_imports_tree = f.read()
        return last_imports_tree

    def _set_last_imports(self, tree):
        compat.makedirs(os.path.dirname(self._last_imports_path()))
        with open(self._last_imports_path(), 'w') as f:
            f.write(tree)

    @asyncio.coroutine
    def do_build(self, runtime, rules):
        """Runs all the build rules, taking their export paths into account.
        Returns the final export path."""
        yield from self.apply_imports(runtime)
        export_path = self.root
        if self.default_rule:
            export_path = yield from self.default_rule.do_build(
                runtime, export_path)
        for rule in rules:
            export_path = yield from rule.do_build(runtime, export_path)
        return export_path

    @asyncio.coroutine
    def get_tree(self, runtime, rules):
        export_path = yield from self.do_build(runtime, rules)
        # It's important that we exclude .peru from the imported files. Imports
        # could by copied into the root of the toplevel project, and that would
        # conflict with the .peru dir there. Also, it's just garbage that the
        # user doesn't want. (But it's important to keep track of lastimports
        # in local overrides. And possibly other stuff in the future.)
        return runtime.cache.import_tree(export_path, excludes=['.peru'])

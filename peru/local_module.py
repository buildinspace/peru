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
    def get_tree(self, runtime):
        return runtime.cache.import_tree(self.root)

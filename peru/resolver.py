import collections

from .remote_module import RemoteModule
from .rule import Rule


class Resolver:
    def __init__(self, scope, cache):
        self.scope = scope
        self.cache = cache

    def resolve_imports_to_treepaths(self, imports):
        # We always want to resolve (and eventually apply) imports in the same
        # order, so that any conflicts or other errors we run into will be
        # deterministic. Sort the imports alphabetically by name, and return
        # the resolved trees in the same order.
        #
        # NB: Resolving imports builds them if they haven't been built before.
        treepaths = []
        for target, path in sorted(imports.items()):
            tree = self.get_tree(target)
            treepath = TreePath(tree, path, target)
            treepaths.append(treepath)
        return tuple(treepaths)

    def merge_import_trees(self, imports):
        treepaths = self.resolve_imports_to_treepaths(imports)
        unified_tree = None
        for import_tree, import_path, target in treepaths:
            unified_tree = self.cache.merge_trees(
                unified_tree, import_tree, import_path)
        return unified_tree

    def apply_imports(self, imports, path, last_imports_tree=None):
        unified_imports_tree = self.merge_import_trees(imports)
        self.cache.export_tree(unified_imports_tree, path, last_imports_tree)
        return unified_imports_tree

    def get_tree(self, target_str):
        target = self.get_target(target_str)
        if isinstance(target, RemoteModule):
            return target.get_tree(self.cache, self)
        elif isinstance(target, Rule):
            parent = self.get_parent(target_str)
            input_tree = parent.get_tree(self.cache, self)
            return target.get_tree(self.cache, self, input_tree)
        else:
            raise NotImplementedError("What is this? " + type(target))

    def get_target(self, target_str):
        if target_str not in self.scope:
            raise RuntimeError("Unknown target: " + repr(target_str))
        return self.scope[target_str]

    def get_parent(self, target_str):
        parent_str = ".".join(target_str.split(".")[:-1])
        if parent_str == "":
            raise RuntimeError('Target "{}" has no parent.'.format(target_str))
        return self.get_target(parent_str)

TreePath = collections.namedtuple("TreePath", ["tree", "path", "target"])

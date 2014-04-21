import os

from .remote_module import RemoteModule
from .rule import Rule


class Resolver:
    def __init__(self, scope, cache):
        self.scope = scope
        self.cache = cache

    def resolve_import_trees(self, imports):
        # Iterate over sorted items so that the order is always consistent.
        # This avoids having different error messages from one run to the next,
        # which you might see if you run into a bug in the cache state.
        return {self.get_tree(target): path
                for target, path in sorted(imports.items())}

    def apply_imports(self, imports, dest):
        import_trees = self.resolve_import_trees(imports)
        # As above, make sure to iterate over imports in sorted order.
        for tree, path in sorted(import_trees.items()):
            import_dest = os.path.join(dest, path)
            # TODO: clean previous trees
            self.cache.export_tree(tree, import_dest)
        return import_trees

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

    def build_locally(self, target_str, path):
        target = self.get_target(target_str)
        if not isinstance(target, Rule) or "." in target_str:
            raise RuntimeError('Target "{}" is not a local rule.'.format(
                target_str))
        target.do_build(self, path)

    def get_target(self, target_str):
        if target_str not in self.scope:
            raise RuntimeError("Unknown target: " + repr(target_str))
        return self.scope[target_str]

    def get_parent(self, target_str):
        parent_str = ".".join(target_str.split(".")[:-1])
        if parent_str == "":
            raise RuntimeError('Target "{}" has no parent.'.format(target_str))
        return self.get_target(parent_str)

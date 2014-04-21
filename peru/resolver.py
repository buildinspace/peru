import os

from .remote_module import RemoteModule
from .rule import Rule


class Resolver:
    def __init__(self, scope, cache):
        self.scope = scope
        self.cache = cache

    def resolve_import_trees(self, imports):
        return {self.get_tree(target): path
                for target, path in imports.items()}

    def apply_imports(self, imports, dest):
        import_trees = self.resolve_import_trees(imports)
        for tree, path in import_trees.items():
            import_dest = os.path.join(dest, path)
            # TODO: clean previous trees
            self.cache.export_tree(tree, import_dest)
        return import_trees

    def get_tree(self, target_str):
        target = self.get_target(target_str)
        if not target:
            raise RuntimeError("Unknown target: " + target_str)

        if isinstance(target, RemoteModule):
            return target.get_tree(self.cache, self)
        elif isinstance(target, Rule):
            parent = self.get_parent(target_str)
            if not parent:
                raise NotImplementedError(
                    "Not sure what to do with the local module yet...")
            input_tree = parent.get_tree(self.cache, self)
            return target.get_tree(self.cache, self, input_tree)
        else:
            raise NotImplementedError("What is this? " + type(target))

    def get_target(self, target_str):
        return self.scope.get(target_str, None)

    def get_parent(self, target_str):
        parent_str = ".".join(target_str.split(".")[:-1])
        return self.get_target(parent_str)

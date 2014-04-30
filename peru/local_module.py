import os

from .rule import Rule


class LocalModule:
    def __init__(self, imports):
        self.imports = imports
        self.path = "."

    def apply_imports(self, resolver):
        last_imports_tree_path = os.path.join(
            resolver.cache.root, "lastimports")
        last_imports_tree = None
        if os.path.exists(last_imports_tree_path):
            with open(last_imports_tree_path) as f:
                last_imports_tree = f.read()

        unified_imports_tree = resolver.apply_imports(
            self.imports, self.path, last_imports_tree)

        with open(last_imports_tree_path, "w") as f:
            f.write(unified_imports_tree)

    def do_build(self, resolver, target_str):
        target = resolver.get_target(target_str)
        if not isinstance(target, Rule) or "." in target_str:
            raise RuntimeError('Target "{}" is not a local rule.'.format(
                target_str))
        target.do_build(self.path)

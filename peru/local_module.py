import os

from . import resolver


class LocalModule:
    def __init__(self, imports, default_rule, path):
        self.imports = imports
        self.default_rule = default_rule
        self.path = path

    def apply_imports(self, runtime):
        last_imports_tree_path = os.path.join(runtime.peru_dir, "lastimports")
        last_imports_tree = None
        if os.path.exists(last_imports_tree_path):
            with open(last_imports_tree_path) as f:
                last_imports_tree = f.read()

        unified_imports_tree = resolver.apply_imports(
            runtime, self.imports, self.path, last_imports_tree)

        with open(last_imports_tree_path, "w") as f:
            f.write(unified_imports_tree)

    def do_build(self, rules):
        """Runs all the build rules, taking their export paths into account.
        Returns the final export path."""
        path = self.path
        if self.default_rule:
            path = self.default_rule.do_build(path)
        for rule in rules:
            path = rule.do_build(path)
        return path

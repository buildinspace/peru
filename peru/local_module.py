import os


class LocalModule:
    def __init__(self, imports, default_rule):
        self.imports = imports
        self.default_rule = default_rule
        self.path = "."

    def apply_imports(self, resolver, *, force=False):
        last_imports_tree_path = os.path.join(
            resolver.cache.root, "lastimports")
        last_imports_tree = None
        if os.path.exists(last_imports_tree_path):
            with open(last_imports_tree_path) as f:
                last_imports_tree = f.read()

        unified_imports_tree = resolver.apply_imports(
            self.imports, self.path, last_imports_tree, force=force)

        with open(last_imports_tree_path, "w") as f:
            f.write(unified_imports_tree)

    def do_build(self, rules):
        if self.default_rule:
            self.default_rule.do_build(self.path)
        for rule in rules:
            rule.do_build(self.path)

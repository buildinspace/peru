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
        module, rules = self.parse_target(target_str)
        tree = module.get_tree(self.cache, self)
        if module.default_rule:
            tree = module.default_rule.get_tree(self.cache, self, tree)
        for rule in rules:
            tree = rule.get_tree(self.cache, self, tree)
        return tree

    def parse_target(self, target_str):
        module_name, *rule_names = target_str.split(":")
        module = self.scope[module_name]
        assert isinstance(module, RemoteModule)
        rules = [self.scope[name] for name in rule_names]
        assert all(isinstance(rule, Rule) for rule in rules)
        return module, rules

    def get_rules(self, rule_names):
        rules = [self.scope[name] for name in rule_names]
        assert all(isinstance(rule, Rule) for rule in rules)
        return rules

TreePath = collections.namedtuple("TreePath", ["tree", "path", "target"])

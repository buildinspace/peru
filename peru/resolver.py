import collections
import textwrap

from .cache import Cache
from .error import PrintableError
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

    def merge_import_trees(self, imports, base_tree=None):
        treepaths = self.resolve_imports_to_treepaths(imports)
        unified_tree = base_tree
        for import_tree, import_path, target in treepaths:
            try:
                unified_tree = self.cache.merge_trees(
                    unified_tree, import_tree, import_path)
            except Cache.MergeConflictError as e:
                raise PrintableError(
                    "merge conflict in import '{}' at '{}':\n\n{}".format(
                        target, import_path, textwrap.indent(e.args[0], "  ")))

        return unified_tree

    def apply_imports(self, imports, path, last_imports_tree=None, *,
                      force=False):
        unified_imports_tree = self.merge_import_trees(imports)
        try:
            self.cache.export_tree(unified_imports_tree, path,
                                   last_imports_tree, force=force)
        except Cache.DirtyWorkingCopyError as e:
            raise PrintableError(
                "imports conflict with the working copy:\n\n" +
                textwrap.indent(e.args[0], "  "))
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
        module = self.get_modules([module_name])[0]
        rules = self.get_rules(rule_names)
        return module, rules

    def get_rules(self, rule_names):
        rules = []
        for name in rule_names:
            if name not in self.scope:
                raise PrintableError("rule '{}' does not exist".format(name))
            rule = self.scope[name]
            if not isinstance(rule, Rule):
                raise PrintableError("'{}' is not a rule".format(name))
            rules.append(rule)
        return rules

    def get_all_modules(self):
        return {m for m in self.scope.values() if isinstance(m, RemoteModule)}

    def get_modules(self, names):
        modules = []
        for name in names:
            if name not in self.scope:
                raise PrintableError("module '{}' does not exist".format(name))
            module = self.scope[name]
            if not isinstance(module, RemoteModule):
                raise PrintableError("'{}' is not a module".format(name))
            modules.append(module)
        return modules

TreePath = collections.namedtuple("TreePath", ["tree", "path", "target"])

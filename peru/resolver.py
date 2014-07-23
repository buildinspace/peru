import collections
import os

from . import cache
from .compat import indent
from .error import PrintableError


def resolve_imports_to_treepaths(runtime, imports):
    # We always want to resolve (and eventually apply) imports in the same
    # order, so that any conflicts or other errors we run into will be
    # deterministic. Sort the imports alphabetically by name, and return
    # the resolved trees in the same order.
    #
    # NB: Resolving imports builds them if they haven't been built before.
    treepaths = []
    for target, path in sorted(imports.items()):
        tree = get_tree(runtime, target)
        treepath = TreePath(tree, path, target)
        treepaths.append(treepath)
    return tuple(treepaths)


def merge_import_trees(runtime, imports, base_tree=None):
    treepaths = resolve_imports_to_treepaths(runtime, imports)
    unified_tree = base_tree
    for import_tree, import_path, target in treepaths:
        try:
            unified_tree = runtime.cache.merge_trees(
                unified_tree, import_tree, import_path)
        except cache.MergeConflictError as e:
            e.msg = "Merge conflict in import '{}' at '{}':\n\n{}".format(
                target, import_path, indent(e.msg, "  "))
            raise

    return unified_tree


def apply_imports(runtime, imports, path, last_imports_tree=None):
    unified_imports_tree = merge_import_trees(runtime, imports)
    try:
        runtime.cache.export_tree(unified_imports_tree, path,
                                  last_imports_tree, force=runtime.force)
    except cache.DirtyWorkingCopyError as e:
        e.msg = ('The working copy is dirty. ' +
                 'To run anyway, use --force/-f\n\n' +
                 indent(e.msg, '  '))
        raise
    return unified_imports_tree


def get_tree(runtime, target_str):
    module, rules = _parse_target(runtime, target_str)
    if module.name in runtime.overrides:
        return _get_override_tree(runtime, module, rules)
    tree = module.get_tree(runtime)
    if module.default_rule:
        tree = module.default_rule.get_tree(runtime, tree)
    for rule in rules:
        tree = rule.get_tree(runtime, tree)
    return tree


def _get_override_tree(runtime, module, rules):
    override_path = runtime.get_override(module.name)
    if not os.path.exists(override_path):
        raise PrintableError(
            "override path for module '{}' does not exist: {}".format(
                module.name, override_path))
    if not os.path.isdir(override_path):
        raise PrintableError(
            "override path for module '{}' is not a directory: {}".format(
                module.name, override_path))
    override_module = module.get_local_override(override_path)
    export_path = override_module.do_build(runtime, rules)
    return runtime.cache.import_tree(export_path)


def _parse_target(runtime, target_str):
    module_name, *rule_names = target_str.split(":")
    module = get_modules(runtime, [module_name])[0]
    rules = get_rules(runtime, rule_names)
    return module, rules


def get_rules(runtime, rule_names):
    rules = []
    for name in rule_names:
        if name not in runtime.scope:
            raise PrintableError('rule "{}" does not exist'.format(name))
        rule = runtime.scope[name]
        # Avoid a circular import.
        if type(rule).__name__ != 'Rule':
            raise PrintableError('"{}" is not a rule'.format(name))
        rules.append(rule)
    return rules


def get_all_modules(runtime):
    return {m for m in runtime.scope.values()
            # Avoid a circular import.
            if type(m).__name__ == 'RemoteModule'}


def get_modules(runtime, names):
    modules = []
    for name in names:
        if name not in runtime.scope:
            raise PrintableError("module '{}' does not exist".format(name))
        module = runtime.scope[name]
        # Avoid a circular import.
        if type(module).__name__ != "RemoteModule":
            raise PrintableError("'{}' is not a module".format(name))
        modules.append(module)
    return modules

TreePath = collections.namedtuple("TreePath", ["tree", "path", "target"])

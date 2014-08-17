from .cache import compute_key, MergeConflictError
from . import compat


def merge_imports_tree(cache, imports, target_trees, base_tree=None):
    '''Take a dictionary of imports and a dictionary of resolved trees and
    merge the unified imports tree. If base_tree is supplied, merge that too.
    There are several reasons for structuring this function the way it is:
        - We want to cache merged trees, so that we don't have to do expensive
          git operations just to compute the tree of a remote module.
        - We don't want to do that caching at a lower level, because we need to
          emit good error messages when there are merge conflicts, and for that
          we need to have target names.
        - LocalModule and RemoteModule need to share this code.
        - This function doesn't do any fetching, so that a remote module can
          fetch its dependencies in parallel with itself before calling this.
    '''
    key = _cache_key(imports, target_trees, base_tree)
    if key in cache.keyval:
        return cache.keyval[key]
    # We always want to merge imports in the same order, so that any conflicts
    # we run into will be deterministic. Sort the imports alphabetically by
    # target name.
    targets = sorted(imports.keys())
    unified_tree = base_tree or cache.empty_tree
    for target in targets:
        tree = target_trees[target]
        path = imports[target]
        try:
            unified_tree = cache.merge_trees(
                unified_tree, tree, path)
        except MergeConflictError as e:
            e.msg = "Merge conflict in import '{}' at '{}':\n\n{}".format(
                target, path, compat.indent(e.msg, "  "))
            raise
    cache.keyval[key] = unified_tree
    return unified_tree


def _cache_key(imports, target_trees, base_tree):
    tree_paths = {target_trees[target]: imports[target] for target in imports}
    return compute_key({
        'base_tree': base_tree,
        'tree_paths': tree_paths,
    })

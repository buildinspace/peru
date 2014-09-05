import textwrap

from .cache import compute_key, MergeConflictError


def merge_imports_tree(cache, imports, target_trees, base_tree=None):
    '''Take an Imports struct and a dictionary of resolved trees and merge the
    unified imports tree. If base_tree is supplied, merge that too. There are
    several reasons for structuring this function the way it is:
        - We want to cache merged trees, so that we don't have to do expensive
          git operations just to check whether a module is in cache.
        - We want tree merging to know about target names, so that it can write
          good error messages when there are conflicts.
        - LocalModule and RemoteModule need to share this code.
        - This function doesn't do any fetching, so that a remote module can
          fetch its imports in parallel with itself before calling this. If
          this was a generator that fetched imports for you, the remote module
          would have to do the final base_tree merge itself, and it wouldn't be
          able to give good error messages for conflicts.'''
    key = _cache_key(imports, target_trees, base_tree)
    if key in cache.keyval:
        return cache.keyval[key]
    # We always want to merge imports in the same order, so that any conflicts
    # we run into will be deterministic. Sort the imports alphabetically by
    # target name.
    unified_tree = base_tree or cache.empty_tree
    for target, path in imports.pairs:
        try:
            unified_tree = cache.merge_trees(
                unified_tree, target_trees[target], path)
        except MergeConflictError as e:
            e.message = "Merge conflict in import '{}' at '{}':\n\n{}".format(
                target, path, textwrap.indent(e.message, "  "))
            raise
    cache.keyval[key] = unified_tree
    return unified_tree


def _cache_key(imports, target_trees, base_tree):
    tree_paths = {target_trees[target]: path for target, path in imports.pairs}
    return compute_key({
        'base_tree': base_tree,
        'tree_paths': tree_paths,
    })

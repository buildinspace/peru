import textwrap

from .cache import compute_key, MergeConflictError


async def merge_imports_tree(cache, imports, target_trees, base_tree=None):
    '''Take an Imports struct and a dictionary of resolved trees and merge the
    unified imports tree. If base_tree is supplied, merge that too. There are a
    couple reasons for structuring this function the way it is:
        - We want to cache merged trees, so that we don't have to do expensive
          git operations just to check whether a module is in cache.
        - We want tree merging to know about target names, so that it can write
          good error messages when there are conflicts.
        - We need to use this for both toplevel imports and recursive module
          imports.
    '''
    key = _cache_key(imports, target_trees, base_tree)
    if key in cache.keyval:
        return cache.keyval[key]
    # We always want to merge imports in the same order, so that any conflicts
    # we run into will be deterministic. Sort the imports alphabetically by
    # target name.
    unified_tree = base_tree or (await cache.get_empty_tree())
    for target, paths in imports.items():
        for path in paths:
            try:
                unified_tree = await cache.merge_trees(
                    unified_tree, target_trees[target], path)
            except MergeConflictError as e:
                message = 'Merge conflict in import "{}" at "{}":\n\n{}'
                e.message = message.format(target, path,
                                           textwrap.indent(e.message, '  '))
                raise
    cache.keyval[key] = unified_tree
    return unified_tree


def _cache_key(imports, target_trees, base_tree):
    tree_paths = tuple(
        (target_trees[target], paths) for target, paths in imports.items())
    return compute_key({
        'base_tree': base_tree,
        'tree_paths': tree_paths,
    })

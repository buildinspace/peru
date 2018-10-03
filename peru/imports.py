import os
from pathlib import Path

from .async_helpers import gather_coalescing_exceptions
from . import compat
from .error import error_context
from .merge import merge_imports_tree


async def checkout(runtime, scope, imports, path):
    imports_tree = await get_imports_tree(runtime, scope, imports)
    last_imports_tree = _get_last_imports(runtime)
    index = _last_imports_index(runtime)
    await runtime.cache.export_tree(
        imports_tree,
        path,
        last_imports_tree,
        force=runtime.force,
        previous_index_file=index)
    _set_last_imports(runtime, imports_tree)


async def get_imports_tree(runtime, scope, imports, base_tree=None):
    target_trees = await get_trees(runtime, scope, imports.keys())
    imports_tree = await merge_imports_tree(runtime.cache, imports,
                                            target_trees, base_tree)
    return imports_tree


async def get_trees(runtime, scope, targets):
    futures = [get_tree(runtime, scope, target) for target in targets]
    trees = await gather_coalescing_exceptions(
        futures, runtime.display, verbose=runtime.verbose)
    return dict(zip(targets, trees))


async def get_tree(runtime, scope, target_str):
    module, rules = await scope.parse_target(runtime, target_str)
    context = 'target "{}"'.format(target_str)
    with error_context(context):
        tree = await module.get_tree(runtime)
        if module.default_rule:
            tree = await module.default_rule.get_tree(runtime, tree)
        for rule in rules:
            tree = await rule.get_tree(runtime, tree)
    return tree


def _last_imports_path(runtime):
    return Path(runtime.state_dir) / 'lastimports'


def _get_last_imports(runtime):
    last_imports_tree = None
    if _last_imports_path(runtime).exists():
        with _last_imports_path(runtime).open() as f:
            last_imports_tree = f.read()
    return last_imports_tree


def _set_last_imports(runtime, tree):
    if tree == _get_last_imports(runtime):
        # Don't modify the lastimports file if the imports haven't changed.
        # This lets you use it as a build stamp for Make.
        return
    compat.makedirs(_last_imports_path(runtime).parent)
    with _last_imports_path(runtime).open('w') as f:
        f.write(tree)


def _last_imports_index(runtime):
    return os.path.join(runtime.state_dir, 'lastimports.index')

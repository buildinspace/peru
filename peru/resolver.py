import asyncio

from .async import stable_gather
from .error import PrintableError


@asyncio.coroutine
def get_trees(runtime, targets):
    futures = [get_tree(runtime, target) for target in targets]
    trees = yield from stable_gather(*futures)
    return dict(zip(targets, trees))


@asyncio.coroutine
def get_tree(runtime, target_str):
    module, rules = _parse_target(runtime, target_str)
    tree = yield from module.get_tree(runtime)
    if module.default_rule:
        tree = yield from module.default_rule.get_tree(runtime, tree)
    for rule in rules:
        tree = yield from rule.get_tree(runtime, tree)
    return tree


def _parse_target(runtime, target_str):
    module_name, *rule_names = target_str.split('|')
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
            if type(m).__name__ == 'Module'}


def get_modules(runtime, names):
    modules = []
    for name in names:
        if name not in runtime.scope:
            raise PrintableError('module "{}" does not exist'.format(name))
        module = runtime.scope[name]
        # Avoid a circular import.
        if type(module).__name__ != 'Module':
            raise PrintableError('"{}" is not a module'.format(name))
        modules.append(module)
    return modules

import os

from .error import PrintableError


def get_trees(runtime, targets):
    return {target: get_tree(runtime, target) for target in targets}


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
    return override_module.get_tree(runtime, rules)


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

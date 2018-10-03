from .error import PrintableError

SCOPE_SEPARATOR = '.'
RULE_SEPARATOR = '|'


class Scope:
    '''A Scope holds the elements that are parsed out of a single peru.yaml
    file. This is kept separate from a Runtime, because recursive modules need
    to work with a Scope that makes sense to them, rather than a single global
    scope.'''

    def __init__(self, modules, rules):
        self.modules = modules
        self.rules = rules

    async def parse_target(self, runtime, target_str):
        '''A target is a pipeline of a module into zero or more rules, and each
        module and rule can itself be scoped with zero or more module names.'''
        pipeline_parts = target_str.split(RULE_SEPARATOR)
        module = await self.resolve_module(runtime, pipeline_parts[0],
                                           target_str)
        rules = []
        for part in pipeline_parts[1:]:
            rule = await self.resolve_rule(runtime, part)
            rules.append(rule)
        return module, tuple(rules)

    async def resolve_module(self,
                             runtime,
                             module_str,
                             logging_target_name=None):
        logging_target_name = logging_target_name or module_str
        module_names = module_str.split(SCOPE_SEPARATOR)
        return (await self._resolve_module_from_names(runtime, module_names,
                                                      logging_target_name))

    async def _resolve_module_from_names(self, runtime, module_names,
                                         logging_target_name):
        next_module = self._get_module_checked(module_names[0])
        for name in module_names[1:]:
            next_scope = await _get_scope_or_fail(runtime, logging_target_name,
                                                  next_module)
            if name not in next_scope.modules:
                _error(logging_target_name, 'module {} not found in {}', name,
                       next_module.name)
            next_module = next_scope._get_module_checked(name)
        return next_module

    async def resolve_rule(self, runtime, rule_str, logging_target_name=None):
        logging_target_name = logging_target_name or rule_str
        *module_names, rule_name = rule_str.split(SCOPE_SEPARATOR)
        scope = self
        location_str = ''
        if module_names:
            module = await self._resolve_module_from_names(
                runtime, module_names, logging_target_name)
            scope = await _get_scope_or_fail(runtime, logging_target_name,
                                             module)
            location_str = ' in module ' + module.name
        if rule_name not in scope.rules:
            _error(logging_target_name, 'rule {} not found{}', rule_name,
                   location_str)
        return scope._get_rule_checked(rule_name)

    def get_modules_for_reup(self, names):
        for name in names:
            if SCOPE_SEPARATOR in name:
                raise PrintableError(
                    'Can\'t reup module "{}"; it belongs to another project.'.
                    format(name))
        return [self._get_module_checked(name) for name in names]

    def _get_module_checked(self, name):
        if name not in self.modules:
            raise PrintableError('Module "{}" doesn\'t exist.', name)
        return self.modules[name]

    def _get_rule_checked(self, name):
        if name not in self.rules:
            raise PrintableError('Rule "{}" doesn\'t exist.', name)
        return self.rules[name]


async def _get_scope_or_fail(runtime, logging_target_name, module):
    scope, imports = await module.parse_peru_file(runtime)
    if not scope:
        _error(logging_target_name, 'module {} is not a peru project',
               module.name)
    return scope


def _error(logging_target_name, text, *text_format_args):
    text = text.format(*text_format_args)
    raise PrintableError('Error in target {}: {}'.format(
        logging_target_name, text))

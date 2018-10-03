from peru.async_helpers import run_task
import peru.scope
import shared


class ScopeTest(shared.PeruTest):
    def test_parse_target(self):
        scope = scope_tree_to_scope({
            'modules': {
                'a': {
                    'modules': {
                        'b': {
                            'modules': {
                                'c': {}
                            },
                            'rules': ['r'],
                        }
                    }
                }
            }
        })
        c, (r, ) = run_task(scope.parse_target(DummyRuntime(), 'a.b.c|a.b.r'))
        assert type(c) is DummyModule and c.name == 'a.b.c'
        assert type(r) is DummyRule and r.name == 'a.b.r'


def scope_tree_to_scope(tree, prefix=""):
    '''This function is for generating dummy scope/module/rule hierarchies for
    testing. A scope tree contains a modules dictionary and a rules list, both
    optional. The values of the modules dictionary are themselves scope trees.
    So if module A contains module B and rule R, that's represented as:

    {
        'modules': {
            'A': {
                'modules': {
                    'B': {},
                },
                'rules': ['R'],
            }
        }
    }
    '''
    modules = {}
    if 'modules' in tree:
        for module_name, sub_tree in tree['modules'].items():
            full_name = prefix + module_name
            new_prefix = full_name + peru.scope.SCOPE_SEPARATOR
            module_scope = scope_tree_to_scope(sub_tree, new_prefix)
            modules[module_name] = DummyModule(full_name, module_scope)
    rules = {}
    if 'rules' in tree:
        for rule_name in tree['rules']:
            full_name = prefix + rule_name
            rules[rule_name] = DummyRule(full_name)
    return peru.scope.Scope(modules, rules)


class DummyModule:
    def __init__(self, name, scope):
        self.name = name
        self.scope = scope

    async def parse_peru_file(self, dummy_runtime):
        return self.scope, None


class DummyRule:
    def __init__(self, name):
        self.name = name


class DummyRuntime:
    pass

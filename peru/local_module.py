from .rule import Rule


class LocalModule:
    def __init__(self, imports):
        self.imports = imports
        self.path = "."

    def apply_imports(self, resolver):
        resolver.apply_imports(self.imports, self.path)

    def do_build(self, resolver, target_str):
        target = resolver.get_target(target_str)
        if not isinstance(target, Rule) or "." in target_str:
            raise RuntimeError('Target "{}" is not a local rule.'.format(
                target_str))
        target.do_build(self.path)

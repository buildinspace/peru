import os
import shutil
import subprocess
import yaml

from . import cache as cache_module
from . import rule


def parse(runtime, filename):
    with open(filename) as f:
        blob = yaml.safe_load(f.read())
    rules = extract_rules(blob)
    modules = extract_modules(runtime, blob)
    return Module(blob, rules, modules=modules)


# Only parses fields like "rule foo". The default rule (just "rule") is left
# in, and parsed by the Rule class.
def extract_rules(blob):
    rules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            inner_blob = blob.pop(field)  # remove the field from blob
            name = parts[1]
            rules[name] = rule.Rule(name, inner_blob)
    return rules


def extract_modules(runtime, blob):
    modules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 3 and parts[1] == "module":
            type_, _, name = parts
            inner_blob = blob.pop(field)  # remove the field from blob
            remote = extract_remote(runtime, type_, inner_blob, name)
            rules = extract_rules(inner_blob)
            modules[name] = Module(inner_blob, rules, name=name, remote=remote)
    return modules


def extract_remote(runtime, type_, blob, module_name):
    if type_ not in runtime.plugins:
        raise RuntimeError("Unknown module type: " + type_)
    plugin = runtime.plugins[type_]
    remote_fields = plugin.extract_fields(blob, module_name)
    return Remote(plugin, remote_fields, module_name)


class Remote:
    def __init__(self, plugin, fields, name):
        self.name = name
        self.plugin = plugin
        self.fields = fields

    def cache_key(self):
        digest = cache_module.compute_key({
            "plugin": self.plugin.name,
            "fields": self.fields,
        })
        return digest

    def get_tree(self, cache):
        key = self.cache_key()
        if key in cache.keyval:
            # tree is already in cache
            return cache.keyval[key]
        tmp_dir = cache.tmp_dir()
        try:
            self.plugin.get_files_callback(self.fields, tmp_dir, self.name)
            tree = cache.put_tree(tmp_dir, self.name)
        finally:
            shutil.rmtree(tmp_dir)
        cache.keyval[key] = tree
        return tree


class Module:
    def __init__(self, blob, rules, *, modules={}, name=None, remote=None):
        field_names = {"imports", "rule"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown module fields: {}".format(
                ", ".join(bad_keys)))
        overlapping_names = rules.keys() & modules.keys()
        if overlapping_names:
            raise RuntimeError("rules and modules with the same name: " +
                               ", ".join(overlapping_names))
        self.fields = blob
        self.rules = rules
        self.modules = modules
        self.name = name
        self.remote = remote
        if "rule" in self.fields:
            self.default_rule = rule.Rule("<default>", self.fields["rule"])
        else:
            self.default_rule = rule.Rule("<default>", {})

    def build(self, runtime, path):
        if len(path) == 0:
            return self.build_rule(runtime, self.default_rule)
        if len(path) == 1 and path[0] in self.rules:
            return self.build_rule(runtime, self.rules[path[0]])
        if path[0] not in self.modules:
            raise RuntimeError("no rule or module named " + path[0])
        return self.modules[path[0]].build(runtime, path[1:])

    # Building a rule is done differently depending on whether the rule is part
    # of the local module, or part of a remote module. For the remote, what we
    # do is build it in an isolated temp dir and save the results into cache.
    # For a local rule, we just build it in the current tree.
    # TODO: Is this the right model? It seems a little complicated...
    def build_rule(self, runtime, rule):
        working_dir = runtime.working_dir
        if self.remote:
            key = self.rule_key(rule)
            if runtime.cache.has(key):
                return
            working_dir = runtime.tmp_dir()
            self.remote.get_files(working_dir)
        env_imports = self.fetch_imports_and_return_env(
            runtime, rule, working_dir)
        if "build" in rule.fields:
            command = rule.fields["build"]
            env = dict(os.environ)
            env.update(env_imports)
            subprocess.check_call(command, shell=True, cwd=working_dir,
                                  env=env)
        if self.remote:
            export_dir = working_dir
            if "export" in rule.fields:
                export_dir = os.path.join(export_dir, rule.fields["export"])
            assert os.path.isdir(export_dir)
            runtime.cache.put(key, export_dir)

    def fetch_imports_and_return_env(self, runtime, rule, working_dir):
        imports = {}
        imports.update(self.fields.get("imports", {}))
        imports.update(rule.fields.get("imports", {}))
        env = {}
        for target, import_path in imports.items():
            parts = target.split('.')
            module = self.modules[parts[0]]
            if len(parts) == 1:
                rule = module.default_rule
            elif len(parts) == 2:
                rule = module.rules[parts[1]]
            else:
                # TODO: Rework this when we support remote peru files.
                raise RuntimeError("We don't support big imports yet.")
            # ensure the rule is in cache
            module.build_rule(runtime, rule)
            # import the build outputs
            key = module.rule_key(rule)
            if import_path[0] == "$":
                # environment import
                dest = runtime.tmp_dir()
                env[import_path[1:]] = dest
            else:
                dest = os.path.join(working_dir, import_path)
                os.makedirs(dest, exist_ok=True)
            runtime.cache.get(key, dest)
        return env

    def rule_key(self, rule):
        data = {
            "remote": self.remote.fields,
            "rule": rule.fields,
        }
        return cache_module.compute_key(data)

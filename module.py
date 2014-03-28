import os
import subprocess
import sys
import tempfile

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "third-party", "PyYAML-3.10", "lib3"))
import yaml

import cache
import rule

def parse(runtime, filename):
    with open(filename) as f:
        blob = yaml.safe_load(f.read())
    rules = extract_rules(blob)
    modules = extract_modules(runtime, blob)
    return Module(blob, rules, modules=modules)

def extract_rules(blob):
    rules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            inner_blob = blob.pop(field) # remove the field from blob
            name = parts[1]
            rules[name] = rule.Rule(inner_blob)
    return rules

def extract_modules(runtime, blob):
    modules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "module":
            inner_blob = blob.pop(field) # remove the field from blob
            name = parts[1]
            remote = extract_remote(runtime, inner_blob, name)
            rules = extract_rules(inner_blob)
            modules[name] = Module(inner_blob, rules, name=name, remote=remote)
    return modules

def extract_remote(runtime, blob, module_name):
    if "type" not in blob:
        raise RuntimeError("Remote modules must have a type.")
    type_ = blob.pop("type")
    if type_ not in runtime.plugins:
        raise RuntimeError("Unknown module type: " + type_)
    plugin = runtime.plugins[type_]
    remote_fields = plugin.extract_fields(blob, module_name)
    return Remote(plugin, remote_fields)

def tmp_dir():
    os.makedirs("/tmp/peru", exist_ok=True)
    return tempfile.mkdtemp(dir="/tmp/peru")

class Remote:
    def __init__(self, plugin, fields):
        self.plugin = plugin
        self.fields = fields

    def get_files(self, path):
        self.plugin.get_files_callback(self.fields, path)

class Module:
    def __init__(self, blob, rules, *, modules={}, name=None, remote=None):
        field_names = {"imports", "default_rule"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown module fields: {}".format(
                ", ".join(bad_keys)))
        self.fields = blob
        self.rules = rules
        self.modules = modules
        self.name = name
        self.remote = remote
        if "default_rule" in self.fields:
            d = self.fields["default_rule"]
            if d not in self.rules:
                raise RuntimeError(
                    "default_rule set to {}, but there is no rule by that name"
                    .format(d))
            self.default_rule = self.rules[d]
        else:
            self.default_rule = rule.Rule({})

    def build(self, runtime, path):
        if len(path) == 0:
            return self.build_rule(runtime, self.default_rule)
        if len(path) == 1 and path[0] in self.rules:
            return self.build_rule(runtime, self.rules[path[0]])
        if path[0] not in self.modules:
            raise RuntimeError("No module named " + path[0])
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
            working_dir = tmp_dir()
            self.remote.get_files(working_dir)
        # TODO: imports here
        if "build" in rule.fields:
            command = rule.fields["build"]
            subprocess.check_call(command, shell=True, cwd=working_dir)
        if self.remote:
            export_dir = working_dir
            if "export" in rule.fields:
                export_dir = os.path.join(export_dir, rule.fields["export"])
            assert os.path.isdir(export_dir)
            runtime.cache.put(key, export_dir)

    def rule_key(self, rule):
        data = {
            "remote": self.remote.fields,
            "rule": rule.fields,
        }
        return cache.compute_key(data)

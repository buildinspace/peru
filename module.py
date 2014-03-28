import os
import sys

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "third-party", "PyYAML-3.10", "lib3"))
import yaml

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

class Remote:
    def __init__(self, plugin, fields):
        self.plugin = plugin
        self.fields = fields

class Module:
    def __init__(self, blob, rules, *, modules={}, name=None, remote=None):
        field_names = {"imports"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown module fields: {}".format(
                ", ".join(bad_keys)))
        self.fields = blob
        self.rules = rules
        self.modules = modules
        self.name = name
        self.remote = remote

import os
import sys

sys.path.append(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "third-party", "PyYAML-3.10", "lib3"))
import yaml

import rule

def parse(filename):
    with open(filename) as f:
        blob = yaml.safe_load(f.read())

    rules = extract_rules(blob)
    return Module(blob, rules)

def extract_rules(blob):
    rules = {}
    for field in list(blob.keys()):
        parts = field.split()
        if len(parts) == 2 and parts[0] == "rule":
            inner_blob = blob.pop(field) # remove the field from blob
            name = parts[1]
            rules[name] = rule.Rule(inner_blob)
    return rules

class Module:
    def __init__(self, blob, rules):
        field_names = {"imports"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown module fields: " + ", ".join(bad_keys))
        self.fields = blob
        self.rules = rules

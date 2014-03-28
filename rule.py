import hashlib
import json
import subprocess

class Rule:
    def __init__(self, blob):
        if blob is None:
            blob = {}
        field_names = {"build", "export", "imports"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown rule fields: " + ", ".join(bad_keys))
        self.fields = blob

import os
import shutil
import subprocess

from . import cache as cache_module


class Rule:
    def __init__(self, name, blob):
        self.name = name
        if blob is None:
            blob = {}
        field_names = {"build", "export", "imports"}
        bad_keys = blob.keys() - field_names
        if bad_keys:
            raise RuntimeError("unknown rule fields: " + ", ".join(bad_keys))
        self.fields = blob

    def cache_key(self, input_tree):
        digest = cache_module.compute_key({
            "input_tree": input_tree,
            "fields": self.fields,
        })
        return digest

    # TODO: Handle imports.
    def get_tree(self, cache, input_tree):
        key = self.cache_key(input_tree)
        if key in cache.keyval:
            return cache.keyval[key]

        tmp_dir = cache.tmp_dir()
        try:
            cache.export_tree(input_tree, tmp_dir)
            if "build" in self.fields:
                subprocess.check_call(self.fields["build"], shell=True,
                                      cwd=tmp_dir)
            export_dir = tmp_dir
            if "export" in self.fields:
                export_dir = os.path.join(tmp_dir, self.fields["export"])
            tree = cache.import_tree(export_dir, self.name)
        finally:
            # TODO: Test that everything in the temp dir gets cleaned.
            shutil.rmtree(tmp_dir)

        cache.keyval[key] = tree
        return tree

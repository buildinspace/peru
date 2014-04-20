import os
import shutil
import subprocess

from . import cache as cache_module


class Rule:
    def __init__(self, name, imports, build_command, export):
        self.name = name
        self.imports = imports
        self.build_command = build_command
        self.export = export

    def cache_key(self, module_tree):
        return cache_module.compute_key({
            # TODO: Figure out how to get import trees in here.
            "module_tree": module_tree,
            "build": self.build_command,
            "export": self.export,
        })

    def build(self, path):
        if self.build_command:
            subprocess.check_call(self.build_command, shell=True, cwd=path)

    # TODO: Handle imports.
    def get_tree(self, cache, input_tree):
        key = self.cache_key(input_tree)
        if key in cache.keyval:
            return cache.keyval[key]

        tmp_dir = cache.tmp_dir()
        try:
            cache.export_tree(input_tree, tmp_dir)
            self.build(tmp_dir)
            export_dir = tmp_dir
            if self.export:
                export_dir = os.path.join(tmp_dir, self.export)
            tree = cache.import_tree(export_dir, self.name)
        finally:
            # TODO: Test that everything in the temp dir gets cleaned.
            shutil.rmtree(tmp_dir)

        cache.keyval[key] = tree
        return tree

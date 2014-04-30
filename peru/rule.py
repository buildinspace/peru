import os
import shutil
import subprocess

from .cache import compute_key


class Rule:
    def __init__(self, name, build_command, export):
        self.name = name
        self.build_command = build_command
        self.export = export

    def cache_key(self, resolver, input_tree):
        return compute_key({
            "input_tree": input_tree,
            "build": self.build_command,
            "export": self.export,
        })

    def do_build(self, resolver, path):
        if self.build_command:
            subprocess.check_call(self.build_command, shell=True, cwd=path)

    def get_tree(self, cache, resolver, input_tree):
        key = self.cache_key(resolver, input_tree)
        if key in cache.keyval:
            return cache.keyval[key]

        tmp_dir = cache.tmp_dir()
        try:
            cache.export_tree(input_tree, tmp_dir)
            self.do_build(resolver, tmp_dir)
            export_dir = tmp_dir
            if self.export:
                export_dir = os.path.join(tmp_dir, self.export)
            tree = cache.import_tree(export_dir)
        finally:
            # TODO: Test that everything in the temp dir gets cleaned.
            shutil.rmtree(tmp_dir)

        cache.keyval[key] = tree
        return tree

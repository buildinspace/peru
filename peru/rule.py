import os
import subprocess

from .cache import compute_key
from .error import PrintableError


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

    def do_build(self, path):
        if not self.build_command:
            return
        try:
            subprocess.check_call(self.build_command, shell=True, cwd=path)
        except subprocess.CalledProcessError as e:
            raise PrintableError("Error in build command: " + str(e))

    def get_tree(self, cache, resolver, input_tree):
        key = self.cache_key(resolver, input_tree)
        if key in cache.keyval:
            return cache.keyval[key]

        with cache.tmp_dir() as tmp_dir:
            cache.export_tree(input_tree, tmp_dir)
            self.do_build(tmp_dir)
            export_dir = tmp_dir
            if self.export:
                export_dir = os.path.join(tmp_dir, self.export)
            if not os.path.exists(export_dir):
                raise RuntimeError(
                    "export dir '{}' doesn't exist".format(self.export))
            tree = cache.import_tree(export_dir)

        cache.keyval[key] = tree
        return tree

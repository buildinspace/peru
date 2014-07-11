import os
import subprocess

from .cache import compute_key
from .error import PrintableError


class Rule:
    def __init__(self, name, build_command, export):
        self.name = name
        self.build_command = build_command
        self.export = export

    def _cache_key(self, input_tree):
        return compute_key({
            "input_tree": input_tree,
            "build": self.build_command,
            "export": self.export,
        })

    def do_build(self, path):
        """Executes the rule and returns the exported directory."""
        if self.build_command:
            try:
                subprocess.check_call(self.build_command, shell=True, cwd=path)
            except subprocess.CalledProcessError as e:
                raise PrintableError("Error in build command: " + str(e))
        if self.export:
            export_path = os.path.join(path, self.export)
            if not os.path.exists(export_path):
                raise PrintableError(
                    "export path for rule '{}' does not exist: {}".format(
                        self.name, export_path))
            if not os.path.isdir(export_path):
                raise PrintableError(
                    "export path for rule '{}' is not a directory: {}"
                    .format(self.name, export_path))
            return export_path
        else:
            return path

    def get_tree(self, runtime, input_tree):
        key = self._cache_key(input_tree)
        if key in runtime.cache.keyval:
            return runtime.cache.keyval[key]

        with runtime.tmp_dir() as tmp_dir:
            runtime.cache.export_tree(input_tree, tmp_dir)
            export_dir = self.do_build(tmp_dir)
            tree = runtime.cache.import_tree(export_dir)

        runtime.cache.keyval[key] = tree
        return tree

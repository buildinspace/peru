#! /usr/bin/env python3

import distutils.dir_util

from peru.plugin_shared import plugin_main


def do_fetch(fields, dest, cache_path):
    path = fields["path"]
    distutils.dir_util.copy_tree(path, dest, preserve_symlinks=True)


required_fields = {"path"}
optional_fields = set()

if __name__ == "__main__":
    plugin_main(required_fields, optional_fields, do_fetch, None)

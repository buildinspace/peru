#! /usr/bin/env python3

import distutils.dir_util

from peru.plugin import parse_plugin_args


if __name__ == '__main__':
    fields, (dest, _) = parse_plugin_args(
        {'path'},
        set())
    path = fields['path']

    distutils.dir_util.copy_tree(path, dest, preserve_symlinks=True)

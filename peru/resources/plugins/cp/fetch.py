#! /usr/bin/env python3

import distutils.dir_util

from peru.plugin_shared import parse_plugin_args


fields, dest, _ = parse_plugin_args(
    required_fields={'path'},
    optional_fields=set())
path = fields['path']

distutils.dir_util.copy_tree(path, dest, preserve_symlinks=True)

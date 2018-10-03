#! /usr/bin/env python3

import distutils.dir_util
import os

distutils.dir_util.copy_tree(
    os.environ['PERU_MODULE_PATH'],
    os.environ['PERU_SYNC_DEST'],
    preserve_symlinks=True)

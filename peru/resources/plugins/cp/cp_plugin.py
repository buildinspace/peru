#! /usr/bin/env python3

import os
import shutil

shutil.copytree(
    os.environ['PERU_MODULE_PATH'],
    os.environ['PERU_SYNC_DEST'],
    symlinks=True,
    dirs_exist_ok=True,
)

#! /usr/bin/env python3

import os

import hg_plugin_shared
from hg_plugin_shared import hg


reup = os.environ.get('PERU_MODULE_REUP') or 'default'
clone = hg_plugin_shared.clone_if_needed(
    os.environ['PERU_MODULE_URL'],
    os.environ['PERU_PLUGIN_CACHE'])
hg('pull', hg_dir=clone)
output = hg('identify', '--debug', '--rev', reup, hg_dir=clone)

print('rev:', output.split()[0])

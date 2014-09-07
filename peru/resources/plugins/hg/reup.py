#! /usr/bin/env python3

import os

import hg_plugin_shared
from hg_plugin_shared import hg

cache_path = os.environ['PERU_PLUGIN_CACHE']

url = os.environ['PERU_MODULE_URL']
reup = os.environ['PERU_MODULE_REUP'] or 'default'

hg_plugin_shared.clone_if_needed(url, cache_path)
hg('pull', hg_dir=cache_path)
output = hg('identify', '--debug', '--rev', reup, hg_dir=cache_path)

print('rev:', output.split()[0])

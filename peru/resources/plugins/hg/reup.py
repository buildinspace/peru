#! /usr/bin/env python3

from peru import plugin_shared

import hg_plugin_shared
from hg_plugin_shared import hg


fields, cache_path = plugin_shared.parse_plugin_args(
    hg_plugin_shared.required_fields,
    hg_plugin_shared.optional_fields)
url, rev, reup = hg_plugin_shared.unpack_fields(fields)

clone = hg_plugin_shared.clone_if_needed(url, cache_path)
hg('pull', hg_dir=clone)
output = hg('identify', '--debug', '--rev', reup, hg_dir=clone)

print('rev:', output.split()[0])

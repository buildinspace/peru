#! /usr/bin/env python3

from peru import plugin_shared

import hg_plugin_shared
from hg_plugin_shared import hg


fields, dest, cache_path = plugin_shared.parse_plugin_args(
    hg_plugin_shared.required_fields,
    hg_plugin_shared.optional_fields)
url, rev, _ = hg_plugin_shared.unpack_fields(fields)

clone = hg_plugin_shared.clone_if_needed(url, cache_path, verbose=True)
if not hg_plugin_shared.already_has_rev(clone, rev):
    print('hg pull', url)
    hg('pull', hg_dir=clone)

# TODO: Should this handle subrepos?
hg('archive', '--type', 'files', '--rev', rev, dest, hg_dir=clone)

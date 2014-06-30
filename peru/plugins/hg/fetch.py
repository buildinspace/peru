#! /usr/bin/env python3

from peru.plugin import parse_plugin_args

from shared import already_has_rev
from shared import clone_if_needed
from shared import hg
from shared import optional_fields
from shared import required_fields
from shared import unpack_fields


if __name__ == '__main__':
    fields, (dest, cache_path) = parse_plugin_args(
        required_fields,
        optional_fields)
    url, rev, _ = unpack_fields(fields)

    clone = clone_if_needed(url, cache_path, verbose=True)
    if not already_has_rev(clone, rev):
        print('hg pull', url)

        hg('pull', hg_dir=clone)

    # TODO: Should this handle subrepos?
    hg('archive', '--type', 'files', '--rev', rev, dest, hg_dir=clone)

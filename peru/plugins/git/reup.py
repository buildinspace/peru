#! /usr/bin/env python3

from peru.plugin import parse_plugin_args

from shared import clone_if_needed
from shared import git
from shared import optional_fields
from shared import required_fields
from shared import unpack_fields


if __name__ == '__main__':
    fields, (cache_path,) = parse_plugin_args(
        required_fields,
        optional_fields)
    url, rev, reup = unpack_fields(fields)

    clone = clone_if_needed(url, cache_path)
    git('fetch', '--prune', git_dir=clone)
    output = git('rev-parse', reup, git_dir=clone)

    print('rev:', output.strip())

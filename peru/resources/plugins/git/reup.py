#! /usr/bin/env python3

from peru import plugin_shared

import git_plugin_shared
from git_plugin_shared import git


fields, cache_path = plugin_shared.parse_plugin_args(
    git_plugin_shared.required_fields,
    git_plugin_shared.optional_fields)
url, rev, reup = git_plugin_shared.unpack_fields(fields)

clone = git_plugin_shared.clone_if_needed(url, cache_path)
git('fetch', '--prune', git_dir=clone)
output = git('rev-parse', reup, git_dir=clone)

print('rev:', output.strip())

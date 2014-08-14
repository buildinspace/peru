#! /usr/bin/env python3

import os

import git_plugin_shared
from git_plugin_shared import git


reup = os.environ.get('PERU_MODULE_REUP') or 'master'
clone = git_plugin_shared.clone_if_needed(
    os.environ['PERU_MODULE_URL'],
    os.environ['PERU_PLUGIN_CACHE'])
git('fetch', '--prune', git_dir=clone)
output = git('rev-parse', reup, git_dir=clone)

print('rev:', output.strip())

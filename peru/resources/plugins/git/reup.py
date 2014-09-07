#! /usr/bin/env python3

import os

import git_plugin_shared
from git_plugin_shared import git

url = os.environ['PERU_MODULE_URL']
reup = os.environ['PERU_MODULE_REUP'] or 'master'

repo_path = git_plugin_shared.clone_if_needed(url)
git('fetch', '--prune', git_dir=repo_path)
output = git('rev-parse', reup, git_dir=repo_path)

print('rev:', output.strip())

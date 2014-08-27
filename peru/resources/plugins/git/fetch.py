#! /usr/bin/env python3

import configparser
import os

import git_plugin_shared
from git_plugin_shared import git


def clone_and_maybe_print(url, cache_path):
    if not git_plugin_shared.has_clone(url, cache_path):
        print('git clone ' + url)
    return git_plugin_shared.clone_if_needed(url, cache_path)


def already_has_rev(repo, rev):
    try:
        # Make sure the rev exists.
        git('cat-file', '-e', rev, git_dir=repo)
        # Get the hash for the rev.
        output = git('rev-parse', rev, git_dir=repo)
    except:
        return False

    # Only return True for revs that are absolute hashes.
    # We could consider treating tags the way, but...
    # 1) Tags actually can change.
    # 2) It's not clear at a glance if something is a branch or a hash.
    # Keep it simple.
    return output.strip() == rev


def checkout_tree(cache_path, dest, url, rev):
    clone = clone_and_maybe_print(url, cache_path)
    if not already_has_rev(clone, rev):
        print('git fetch ' + url)
        git('fetch', '--prune', git_dir=clone)
    git('--work-tree=' + dest, 'checkout', rev, '--', '.', git_dir=clone)
    checkout_subrepos(cache_path, clone, rev, dest)


def checkout_subrepos(cache_path, clone_path, rev, work_tree):
    gitmodules = os.path.join(work_tree, '.gitmodules')
    if not os.path.exists(gitmodules):
        return

    parser = configparser.ConfigParser()
    parser.read(gitmodules)
    for section in parser.sections():
        sub_relative_path = parser[section]['path']
        sub_full_path = os.path.join(work_tree, sub_relative_path)
        sub_url = parser[section]['url']
        ls_tree = git('ls-tree', '-r', rev, sub_relative_path,
                      git_dir=clone_path)
        sub_rev = ls_tree.split()[2]
        checkout_tree(cache_path, sub_full_path, sub_url, sub_rev)


checkout_tree(
    os.environ['PERU_PLUGIN_CACHE'],
    os.environ['PERU_FETCH_DEST'],
    os.environ['PERU_MODULE_URL'],
    os.environ.get('PERU_MODULE_REV') or 'master')

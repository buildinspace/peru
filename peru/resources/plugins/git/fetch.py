#! /usr/bin/env python3

import configparser
import os

import git_plugin_shared
from git_plugin_shared import git


def clone_and_maybe_print(url):
    if not git_plugin_shared.has_clone(url):
        print('git clone ' + url)
    return git_plugin_shared.clone_if_needed(url)


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


def checkout_tree(url, rev, dest):
    repo_path = clone_and_maybe_print(url)
    if not already_has_rev(repo_path, rev):
        print('git fetch ' + url)
        git('fetch', '--prune', git_dir=repo_path)
    # If we just use `git checkout rev -- .` here, we get an error when rev is
    # an empty commit.
    git('--work-tree=' + dest, 'read-tree', rev, git_dir=repo_path)
    git('--work-tree=' + dest, 'checkout-index', '--all', git_dir=repo_path)
    checkout_subrepos(repo_path, rev, dest)


def checkout_subrepos(repo_path, rev, work_tree):
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
                      git_dir=repo_path)
        sub_rev = ls_tree.split()[2]
        checkout_tree(sub_url, sub_rev, sub_full_path)


checkout_tree(
    os.environ['PERU_MODULE_URL'],
    os.environ.get('PERU_MODULE_REV') or 'master',
    os.environ['PERU_FETCH_DEST'])

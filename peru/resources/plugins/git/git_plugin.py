#! /usr/bin/env python3

from collections import namedtuple
import configparser
import hashlib
import os
import subprocess
import sys

Result = namedtuple("Result", ["returncode", "output"])


def git(*args, git_dir=None, capture_output=False, checked=True):
    # Avoid forgetting this arg.
    assert git_dir is None or os.path.isdir(git_dir)

    command = ['git']
    if git_dir:
        command.append('--git-dir={0}'.format(git_dir))
    command.extend(args)

    stdout = subprocess.PIPE if capture_output else None
    # Always let stderr print to the caller.
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        universal_newlines=True)
    output, _ = process.communicate()
    if checked and process.returncode != 0:
        sys.exit(1)

    return Result(process.returncode, output)


def has_clone(url):
    return os.path.exists(repo_cache_path(url))


def clone_if_needed(url):
    repo_path = repo_cache_path(url)
    if not has_clone(url):
        # We look for this print in test, to count the number of clones we did.
        print('git clone ' + url)
        git('clone', '--mirror', '--progress', url, repo_path)
    return repo_path


def repo_cache_path(url):
    # Because peru gives each plugin a unique cache dir based on its cacheable
    # fields (in this case, url) we could clone directly into cache_root.
    # However, because the git plugin needs to handle git submodules as well,
    # it still has to separate things out by repo url.
    CACHE_ROOT = os.environ['PERU_PLUGIN_CACHE']

    # If we just concatenate the escaped repo URL into the path, we start to
    # run up against the 260-character path limit on Windows.
    url_hash = hashlib.sha1(url.encode()).hexdigest()

    return os.path.join(CACHE_ROOT, url_hash)


def git_fetch(url, repo_path):
    print('git fetch ' + url)
    git('fetch', '--prune', git_dir=repo_path)


def already_has_rev(repo, rev):
    # Make sure the rev exists.
    cat_result = git('cat-file', '-e', rev, git_dir=repo, checked=False)
    if cat_result.returncode != 0:
        return False
    # Get the hash for the rev.
    parse_result = git(
        'rev-parse', rev, git_dir=repo, checked=False, capture_output=True)
    if parse_result.returncode != 0:
        return False
    # Only return True for revs that are absolute hashes.
    # We could consider treating tags the way, but...
    # 1) Tags actually can change.
    # 2) It's not clear at a glance if something is a branch or a tag.
    # Keep it simple.
    return parse_result.output.strip() == rev


def checkout_tree(url, rev, dest):
    repo_path = clone_if_needed(url)
    if not already_has_rev(repo_path, rev):
        git_fetch(url, repo_path)
    # If we just use `git checkout rev -- .` here, we get an error when rev is
    # an empty commit.
    git('--work-tree=' + dest, 'read-tree', rev, git_dir=repo_path)
    git('--work-tree=' + dest, 'checkout-index', '--all', git_dir=repo_path)
    checkout_submodules(url, repo_path, rev, dest)


def checkout_submodules(parent_url, repo_path, rev, work_tree):
    if os.environ['PERU_MODULE_SUBMODULES'] == 'false':
        return

    gitmodules = os.path.join(work_tree, '.gitmodules')
    if not os.path.exists(gitmodules):
        return

    parser = configparser.ConfigParser()
    parser.read(gitmodules)
    for section in parser.sections():
        sub_relative_path = parser[section]['path']
        sub_full_path = os.path.join(work_tree, sub_relative_path)
        raw_sub_url = parser[section]['url']
        # Submodules can begin with ./ or ../, in which case they're relative
        # to the parent's URL. Handle this case.
        sub_url = expand_relative_submodule_url(raw_sub_url, parent_url)
        ls_tree = git(
            'ls-tree',
            rev,
            sub_relative_path,
            git_dir=repo_path,
            capture_output=True).output
        # Normally when you run `git submodule add ...`, git puts two things in
        # your repo: an entry in .gitmodules, and a commit object at the
        # appropriate path inside your repo. However, it's possible for those
        # two to get out of sync, especially if you use mv/rm on a directory
        # followed by `git add`, instead of the smarter `git mv`/`git rm`. If
        # we run into one of these missing submodules, just skip it.
        if len(ls_tree.strip()) == 0:
            print('WARNING: submodule ' + sub_relative_path +
                  ' is configured in .gitmodules, but missing in the repo')
            continue
        sub_rev = ls_tree.split()[2]
        checkout_tree(sub_url, sub_rev, sub_full_path)


# According to comments in its own source code, git's implementation of
# relative submodule URLs is full of unintended corner cases. See:
# https://github.com/git/git/blob/v2.20.1/builtin/submodule--helper.c#L135
#
# We absolutely give up on trying to replicate their logic -- which probably
# isn't stable in any case -- and instead we just leave the dots in and let the
# host make sense of it. A quick sanity check on GitHub confirmed that that
# seems to work for now.
def expand_relative_submodule_url(raw_sub_url, parent_url):
    if not raw_sub_url.startswith("./") and not raw_sub_url.startswith("../"):
        return raw_sub_url
    new_path = parent_url
    if not new_path.endswith("/"):
        new_path += "/"
    new_path += raw_sub_url
    return new_path


def plugin_sync(url, rev):
    checkout_tree(url, rev, os.environ['PERU_SYNC_DEST'])


def plugin_reup(url, reup):
    reup_output = os.environ['PERU_REUP_OUTPUT']
    repo_path = clone_if_needed(url)
    git_fetch(url, repo_path)
    output = git(
        'rev-parse', reup, git_dir=repo_path, capture_output=True).output
    with open(reup_output, 'w') as out_file:
        print('rev:', output.strip(), file=out_file)


def git_default_branch(url) -> str:
    """
    This function checks if the default branch is master.
    If it is not found, then it assumes it is main.
    For other default branches, user should use the 'rev' option.

    Args:
        url (str): url from the target repository to be checked.
    Returns:
        str: returns a possible match for the git default branch.
    """
    repo_path = clone_if_needed(url)
    output = git('show-ref', '--verify', '--quiet', 'refs/heads/master',
                 git_dir=repo_path, checked=False, capture_output=True)
    if output.returncode == 0:
        return 'master'
    else:
        return 'main'


def main():
    URL = os.environ['PERU_MODULE_URL']
    default_branch = git_default_branch(URL)
    REV = os.environ['PERU_MODULE_REV'] or default_branch
    REUP = os.environ['PERU_MODULE_REUP'] or default_branch

    command = os.environ['PERU_PLUGIN_COMMAND']
    if command == 'sync':
        plugin_sync(URL, REV)
    elif command == 'reup':
        plugin_reup(URL, REUP)
    else:
        raise RuntimeError('Unknown command: ' + repr(command))


if __name__ == "__main__":
    main()

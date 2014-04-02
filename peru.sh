#! /bin/bash

# This script runs peru straight out of the repository, for testing.

repo_root=$(dirname $(realpath $BASH_SOURCE))

PYTHONPATH="$repo_root" "$repo_root/bin/peru" "$@"

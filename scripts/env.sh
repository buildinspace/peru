#! /usr/bin/env bash

# Puts the repo and third-party paths in PYTHONPATH for running peru from the repo.

repo_root="$(dirname $(realpath $BASH_SOURCE))/.."
third_party_path="$repo_root/third-party"

"$repo_root/scripts/bootstrap.sh"

export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$repo_root:$third_party_path"

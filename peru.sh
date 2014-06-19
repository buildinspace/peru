#! /usr/bin/env bash

# This script runs peru from the local repo.

set -e

repo_root="$(dirname $(realpath $BASH_SOURCE))"
source "$repo_root/scripts/env.sh"

"$repo_root/bin/peru" "$@"

#! /usr/bin/env bash

# Run peru from the repo.

set -e

repo_root=$(dirname $(realpath $BASH_SOURCE))

source "$repo_root/scripts/env.sh"

"$repo_root/bin/peru" "$@"

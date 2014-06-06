#! /bin/bash

# This script runs peru straight out of the repository, for testing.

set -e

repo_root=$(dirname $(realpath $BASH_SOURCE))
source "$repo_root/scripts/env.sh"

"$repo_root/bin/peru" "$@"

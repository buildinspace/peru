#! /usr/bin/env bash

set -e

# Unset any PERU_* environment variables to avoid messing up tests.
for var in `env | grep PERU_ | cut -d = -f 1` ; do
  unset $var
done

repo_root="$(dirname $(realpath $BASH_SOURCE))"
source "$repo_root/scripts/env.sh"

python3 -m unittest discover --start peru

flake8 $(find peru -name '*.py')

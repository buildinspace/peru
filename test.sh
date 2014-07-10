#! /usr/bin/env bash

# Run the test suite.

set -e

# Unset any PERU_* environment variables to make sure test runs are consistent.
for var in `env | grep PERU_ | cut -d = -f 1` ; do
  unset $var
done

repo_root=$(dirname $(realpath $BASH_SOURCE))

source "$repo_root/scripts/env.sh"

python3 -m unittest discover --start tests

flake8 peru tests

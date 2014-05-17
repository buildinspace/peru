#! /bin/bash

set -e

# Unset any PERU_* environment variables, to avoid messing up tests.
for var in `env | grep PERU_ | cut -d = -f 1` ; do
  unset $var
done

python3 -m unittest discover --start peru

flake8 $(find peru -name '*.py')

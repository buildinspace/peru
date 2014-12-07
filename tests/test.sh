#! /usr/bin/env bash

# Run the test suite.

set -e

# Unset any PERU_* environment variables to make sure test runs are consistent.
for var in `env | grep PERU_ | cut -d = -f 1` ; do
  unset $var
done

cd $(dirname "$BASH_SOURCE")/..

source scripts/env.sh

export PYTHONASYNCIODEBUG=1

# Make sure tests don't create random untracked files in the project. I've
# missed this before, and it's hard to track down the offending test later.
showuntracked() {
  git ls-files --other --directory --exclude-standard
}
old_untracked=`showuntracked`

coverage run -m unittest discover --start tests --catch "$@"

new_untracked=`showuntracked`
if [[ "$old_untracked" != "$new_untracked" ]] ; then
  echo Tests created untracked files:
  comm -13 <(echo "$old_untracked") <(echo "$new_untracked")
  exit 1
fi

flake8 peru tests

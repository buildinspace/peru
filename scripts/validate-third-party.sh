#! /usr/bin/env bash

# Check the contents of third-party/ against what's specified in peru.yaml.
#
# We would love to have peru fetch all of its own dependencies, but that leads
# us to a bootstrapping problem: We can't run peru until it's dependencies are
# present. To work around that, we define dependencies in peru.yaml, and we
# also check them in. That means we could get into a state where what's checked
# in doesn't match what's in peru.yaml, which could cause all sorts of trouble.
#
# This test helps us avoid that problem. It runs a fresh sync of our peru.yaml
# and compares the result to what we have in the repo, to make sure they match.
# This runs as part of our Travis tests. The expected workflow is that commits
# that change peru.yaml should also commit the new third-party, or else they'll
# break this test.

set -e

cd $(dirname "$BASH_SOURCE")/..
repo_root=`pwd`

test_root=/tmp/peru/validate
mkdir -p "$test_root"
found_dir=$(mktemp -d "$test_root"/found.XXXXXX)
expected_dir=$(mktemp -d "$test_root"/expected.XXXXXX)

# Only copy files not ignored by git into the found directory. This avoids
# getting confused by *.pyc files and the like.
echo Copying third-party to $found_dir
# Handling filenames in a whitespace-safe way is extremely tricky.  See:
# http://mywiki.wooledge.org/BashFAQ/020
while IFS= read -r -d $'\0' file ; do
  if [[ ! -e "$file" ]] ; then
    continue  # Don't error out here on a removed file.
  fi
  mkdir -p "$found_dir/$(dirname "$file")"
  cp "$file" "$found_dir/$file"
done < <(git ls-files -z --cached --other --exclude-standard third-party)

# Do a real peru sync in the expected directory.
echo Syncing third-party to $expected_dir
cp peru.yaml "$expected_dir"
cd "$expected_dir"
# Sync quietly, to spare Travis from a lot of junk output.
"$repo_root/peru.py" sync -q
# The peru.yaml file and the .peru dir won't be in the found dir, so get rid of
# them here.
rm -rf peru.yaml .peru

# Compare the contents of expected and found. Errors out if there's a
# difference.
diff --recursive "$expected_dir" "$found_dir"
echo SUCCESS: third-party/ and peru.yaml are in sync.

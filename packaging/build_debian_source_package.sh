#! /usr/bin/env bash

# $ build_debian_source_package.sh [series [package-version]]
# Generates a Debian source package suitable for upload to a Launchpad PPA. This
# script only builds the package artifacts, it does NOT upload them. Use dput to
# upload to a PPA after building.
# See https://launchpad.net/~buildinspace/+archive/ubuntu/peru

set -e

# Change to the repo root directory.
cd $(dirname "$BASH_SOURCE")/..
repo_root=`pwd`

# Bail if the repo is dirty.
if [ -n "$(git status --porcelain)" ] ; then
  git status
  echo "The source repository is dirty. Aborting."
  exit 1
fi

# Get the current version from the repo. Get the series and package version from
# the command line, otherwise assume "utopic" and version "1".
peru_version=$(<peru/VERSION)
package_version="${2:-1}"
series="${1:-utopic}"

# Create a temporary directory for the build.
tmp=/tmp/peru/ppa
mkdir -p "$tmp"
build_root=`mktemp -d "$tmp"/XXXXXX`
export_root="$build_root"/peru-"$peru_version"

echo "Building Debian source package at ${build_root}"

# Export the repo to the build directory and copy the control files.
git checkout-index -a --prefix="$export_root"/
# TODO: Symlinking debian/ seems to break dpkg-buildpackage. Just copy.
cp -R "$export_root"/packaging/debian "$export_root"/debian

# Change to the root directory of the exported repo.
cd "$export_root"

# Update the changelog version and prompt for a change description.
dch --no-conf -v "$peru_version"-"$package_version" -D "$series"

# Pack the original tarball.
tar cfhJ \
  "$build_root"/peru_"$peru_version".orig.tar.xz \
  ../$(basename "$export_root")

# Build a source package. Note that other package types could easily be built at
# this step as well.
dpkg-buildpackage -S


# Copy the modified changelog to the repo.
cp "$export_root"/debian/changelog "$repo_root"/packaging/debian/changelog

# Done! Change to the repo root directory, diff the changes, and display the
# build directory.
cd "$repo_root" && git diff
echo "SUCCESS. Debian source package built at ${build_root}"

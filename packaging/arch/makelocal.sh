#! /bin/bash

# By default, makepkg clones the source repo from github before building. To
# package your local copy of the sources (including any changes you've made),
# use this script.
#
# See `man makepkg` for relevant options, like -d to ignore missing
# dependencies. (The only dependency needed for packaging is python.)

set -e

cd $(dirname "$BASH_SOURCE")
rm -rf src
mkdir src
ln -s ../../.. src/peru

makepkg -e "$@"

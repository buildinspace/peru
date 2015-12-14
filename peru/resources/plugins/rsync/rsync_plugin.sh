#! /usr/bin/env bash

# The cp plugin is implemented in Python. This is a similar plugin implemented
# in bash, as an example of how to implement plugins in other languages, and to
# force us to keep our plugin interface simple. Not intended for serious use.

set -e -u -o pipefail

# Don't perform the copy without a source. Generally, plugins should not need
# to worry about this, and peru should ensure that required fields are set, but
# the validation may break, and that results in a destructive rsync command
# that will copy root to the destination.
if [ -z "$PERU_MODULE_PATH" ]; then
  echo >&2 "No source path has been set for rsync. Aborting."
  exit 1
fi

# Do the copy. Always append a trailing slash to the path, so that the
# contents are copied rather than the directory itself.
rsync -r "$PERU_MODULE_PATH/" "$PERU_SYNC_DEST"

#! /usr/bin/env bash

# The cp plugin is implemented in Python. This is a similar plugin implemented
# in bash, as an example of how to implement plugins in other languages, and to
# force us to keep our plugin interface simple. Not intended for serious use.

set -e

# Command line arguments before the "--" are plugin fields. Parse them.
while [[ "$1" != "--" ]] ; do
  name="$1"
  shift
  val="$1"
  shift
  case "$name" in
    path)
      path="$val"
      ;;
    *)
      echo unrecognized rsync field: $1 >&2
      exit 1
      ;;
  esac
done
if [[ -z "$path" ]] ; then
  echo path field is required >&2
  exit 1
fi

shift  # the "--"

# Command line arguments after the "--" are commands and command args.
command="$1"
shift
if [[ "$command" != "fetch" ]] ; then
  echo command $command is not supported >&2
  exit 1
fi

dest="$1"
shift
cache_path="$1"  # unused
shift

# Do the copy. Always append a trailing slash to $path, so that the contents
# are copied rather than the directory itself.
rsync -r "$path/" "$dest"

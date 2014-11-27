#! /usr/bin/env bash

# Run peru from the repo.

set -e

realpath() {
  # We need realpath for this script because we expect people to symlink it.
  # Most systems don't have realpath by default. Use this replacement adapted
  # from http://stackoverflow.com/a/1116890/823869. Parens contain the cd.
  (
    TARGET_FILE="$1"
    cd "$(dirname "$TARGET_FILE")"
    TARGET_FILE="$(basename "$TARGET_FILE")"
    while [ -L "$TARGET_FILE" ]; do
        TARGET_FILE="$(readlink "$TARGET_FILE")"
        cd "$(dirname "$TARGET_FILE")"
        TARGET_FILE="$(basename "$TARGET_FILE")"
    done
    PHYS_DIR="$(pwd -P)"
    RESULT="$PHYS_DIR/$TARGET_FILE"
    echo "$RESULT"
  )
}

repo_root=$(dirname $(realpath $BASH_SOURCE))

source "$repo_root/scripts/env.sh"

python3 -c "import peru.main; peru.main.main()" "$@"

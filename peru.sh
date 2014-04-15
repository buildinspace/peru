#! /bin/bash

# This script runs peru straight out of the repository, for testing.

repo_root=$(dirname $(realpath $BASH_SOURCE))

yaml_path="$repo_root/third-party/PyYAML-3.10/lib3"

PYTHONPATH="$repo_root:$yaml_path" "$repo_root/bin/peru" "$@"

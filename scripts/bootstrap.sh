#! /usr/bin/env bash

# Fetches libs needed to bootstrap peru using pip3 and puts them in bootstrap/.
# Then uses peru to fetch libs as defined in peru.yaml.
# This allows peru to fetch its own libs and run directly from the repo.

repo_root="$(dirname $(realpath $BASH_SOURCE))/.."
third_party_path="$repo_root/third-party"

# Check for yaml module.
if [[ ! -e "$third_party_path/yaml" ]] ; then
    # Check for pip3.
    if ! type "pip3" > /dev/null ; then
        echo >&2 "pip3 not found. Can't fetch pyyaml. Aborting." ; exit 1 ;
    fi

    echo >&2 "Bootstrapping."

    bootstrap_path="$repo_root/bootstrap"
    mkdir "$bootstrap_path"

    # Fetch pyyaml with pip3 into bootstrap/.
    pip3 install "pyyaml>=3.10" -t "$bootstrap_path" > /dev/null

    # Stash PYTHONPATH and add bootstrap/ to the path.
    clean_python_path="$PYTHONPATH"
    export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$repo_root:$bootstrap_path"

    # Fetch pyyaml with peru into third-party/.
    # See peru.yaml.
    "$repo_root/bin/peru" sync --force

    # Restore PYTHONPATH.
    export PYTHONPATH="$clean_python_path"

    rm -rf "$bootstrap_path"
fi

# Put local deps into PYTHONPATH.

repo_root="$(realpath "$(dirname "$BASH_SOURCE")/..")"
third_party_path="$repo_root/third-party"

export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$repo_root:$third_party_path"

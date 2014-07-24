# Put local deps into PYTHONPATH.

repo_root="$(cd $(dirname "$BASH_SOURCE")/.. && pwd)"
third_party_path="$repo_root/third-party"

export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$repo_root:$third_party_path"

# Put local deps into PYTHONPATH.

repo_root="$(realpath "$(dirname "$BASH_SOURCE")/..")"
yaml_path="$repo_root/third-party/PyYAML-3.10/lib3"

export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$repo_root:$yaml_path"

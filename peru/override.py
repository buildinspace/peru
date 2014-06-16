import os
import yaml


def _overrides_path(peru_dir):
    return os.path.join(peru_dir, "overrides")


def get_overrides(peru_dir):
    if not os.path.exists(_overrides_path(peru_dir)):
        return {}
    with open(_overrides_path(peru_dir)) as f:
        overrides_dict = yaml.safe_load(f)
    return overrides_dict


def _write_overrides(peru_dir, overrides):
    with open(_overrides_path(peru_dir), "w") as f:
        yaml.dump(overrides, f, default_flow_style=False)


def set_override(peru_dir, name, path):
    overrides = get_overrides(peru_dir)
    overrides[name] = path
    _write_overrides(peru_dir, overrides)


def delete_override(peru_dir, name):
    overrides = get_overrides(peru_dir)
    if name in overrides:
        del overrides[name]
    _write_overrides(peru_dir, overrides)

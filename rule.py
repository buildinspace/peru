import subprocess

class Rule:
    field_names = {"build", "export"}

    def __init__(self, d):
        bad_keys = d.keys() - field_names
        if bad_keys:
            raise RuntimeError("unrecognized rule fields: " +
                               ", ".join(bad_keys))

    def build(path):
        subprocess.check_call(build, shell=True, cwd=path)

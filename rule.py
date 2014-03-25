import hashlib
import json
import subprocess

import cache

class Rule:
    field_names = {"build", "export"}

    def __init__(self, parent, d):
        bad_keys = d.keys() - field_names
        if bad_keys:
            raise RuntimeError("unrecognized rule fields: " +
                               ", ".join(bad_keys))
        self.parent = parent
        self.fields = d

    def cache_key(self):
        all_data = dict(self.fields)
        all_data.update(parent.fields)

        # To hash this dictionary of fields, serialize it as a JSON string, and
        # take the SHA1 of that string. Dictionary key order is unspecified, so
        # "sort_keys" keeps our hash stable. Specifying separators makes the
        # JSON slightly more compact, and protects us against changes in the
        # default.  "ensure_ascii" defaults to true, so specifying it just
        # protects us from changes in the default.
        json_representation = json.dumps(all_data, sort_keys=True,
                                         ensure_ascii=True,
                                         separators=(',', ':'))
        sha1 = hashlib.sha1()
        sha1.update(json_representation.encode("utf8"))
        return sha1.hexdigest()


    def build(path):
        key = self.cache_key()
        if cache.has_cached_files(key):
            return key

        if "build" in self.fields:
            subprocess.check_call(self.fields["build"], shell=True, cwd=path)
        if "export" in self.fields:
            export_path = os.path.join(path, self.fields["export"])
            if not os.path.exists(export_path):
                raise RuntimeError(export_path + " does not exist.")
            if not os.path.isdir(export_path):
                raise RuntimeError(export_path + " is not a directory.")
            return export_path
        else:
            return path

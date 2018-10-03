import os

import peru.compat as compat
import shared


class CompatTest(shared.PeruTest):
    def test_makedirs(self):
        tmp_dir = shared.tmp_dir()
        foo_dir = os.path.join(tmp_dir, "foo")
        compat.makedirs(foo_dir)
        os.chmod(foo_dir, 0o700)
        # Creating the dir again should be a no-op even though the permissions
        # have changed.
        compat.makedirs(foo_dir)

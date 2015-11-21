import contextlib
import os
import shutil
import tempfile

from . import compat


class KeyVal:
    '''A generic way to store key-value pairs on disk. Just creates files in a
    folder whose names are the keys and whose contents are the values.'''

    def __init__(self, root, tmp_dir):
        self._root = root
        self._tmp_dir = tmp_dir
        compat.makedirs(root)
        compat.makedirs(tmp_dir)

    def __getitem__(self, key):
        with open(self._path(key)) as f:
            return f.read()

    def __setitem__(self, key, val):
        # Write to a tmp file first, to avoid partial reads.
        tmp_path = self._tmp_file()
        with open(tmp_path, "w") as f:
            f.write(val)
        shutil.move(tmp_path, self._path(key))

    def __delitem__(self, key):
        if os.path.exists(self._path(key)):
            os.remove(self._path(key))

    def __contains__(self, key):
        return os.path.isfile(self._path(key))

    def __iter__(self):
        return iter(os.listdir(self._root))

    def __len__(self):
        return len(os.listdir(self._root))

    def _path(self, key):
        return os.path.join(self._root, key)

    def _tmp_file(self):
        fd, path = tempfile.mkstemp(dir=self._tmp_dir)
        os.close(fd)
        return path

    @contextlib.contextmanager
    def tmp_dir_context(self):
        try:
            path = tempfile.mkdtemp(dir=self._tmp_dir)
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

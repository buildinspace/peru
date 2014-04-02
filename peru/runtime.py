import os
import sys
import tempfile

from . import cache
from . import plugin

class Runtime:
    def __init__(self):
        self.verbose = "-v" in sys.argv or "--verbose" in sys.argv
        cache_root = os.getenv("PERU_CACHE_NAME") or ".peru-cache"
        self.cache = cache.Cache(cache_root)
        self.plugins = plugin.load_plugins(self)
        self.working_dir = "."

    def log(self, msg):
        if self.verbose:
            print(msg)

    def tmp_dir(self):
        os.makedirs("/tmp/peru", exist_ok=True)
        temp = tempfile.mkdtemp(dir="/tmp/peru")
        return temp

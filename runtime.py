import plugin
import sys

import cache

class Runtime:
    def __init__(self):
        self.verbose = "-v" in sys.argv or "--verbose" in sys.argv
        self.peru_cache_root = cache.cache_root()
        self.plugins = plugin.load_plugins(self)

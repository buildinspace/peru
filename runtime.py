import plugin
import sys

class Runtime:
    def __init__(self):
        self.verbose = "-v" in sys.argv or "--verbose" in sys.argv
        self.peru_cache_root = os.getenv("PERU_CACHE_NAME") or ".peru-cache"
        self.plugins = plugin.load_plugins(self)

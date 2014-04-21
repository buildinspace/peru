from . import plugin


class Runtime:
    def __init__(self, cache):
        self.verbose = True
        self.cache = cache
        self.plugins = plugin.load_plugins(self)
        self.working_dir = "."

    def log(self, msg):
        if self.verbose:
            print(msg)

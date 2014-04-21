#! /usr/bin/env python3

import os
import sys

from .cache import Cache
from .parser import Parser
from .resolver import Resolver
from .runtime import Runtime


def main():
    peru_file = os.getenv("PERU_FILE") or "peru.yaml"
    if not os.path.isfile(peru_file):
        print(peru_file + " not found.")
        sys.exit(1)
    cache_root = os.getenv("PERU_CACHE") or ".peru-cache"
    cache = Cache(cache_root)
    runtime = Runtime(cache)
    parser = Parser(runtime.plugins)
    local_module = parser.parse_file(peru_file)
    resolver = Resolver(local_module.scope, cache)

    path = "./"
    resolver.apply_imports(local_module.imports, path)
    if len(sys.argv) > 1:
        for target_str in sys.argv[1:]:
            resolver.build_locally(target_str, path)

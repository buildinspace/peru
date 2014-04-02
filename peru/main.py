#! /usr/bin/env python3

import os
import sys

from . import runtime
from . import module

def main():
    peru_file_name = os.getenv("PERU_FILE_NAME") or "peru.yaml"
    if not os.path.isfile(peru_file_name):
        print(peru_file_name + " not found.")
        sys.exit(1)
    r = runtime.Runtime()
    m = module.parse(r, peru_file_name)
    if len(sys.argv) > 1:
        target = sys.argv[1].split('.')
    else:
        target = []
    m.build(r, target)

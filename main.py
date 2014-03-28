#! /usr/bin/env python3

import os
import sys

import runtime
import module

def main():
    r = runtime.Runtime()
    peru_file_name = os.getenv("PERU_FILE_NAME") or "peru"
    m = module.parse(r, peru_file_name)
    if len(sys.argv) > 1:
        target = sys.argv[1].split('.')
    else:
        target = []
    m.build(r, target)

if __name__ == '__main__':
    main()

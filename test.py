#! /usr/bin/python3

import os
import sys
import shutil
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__),
                             "third-party/PyYAML-3.10/lib3"))

from peru.runtime import Runtime
from peru.parser import Parser
from peru.resolver import Resolver


cache_path = "/tmp/testcache"
if os.path.exists(cache_path):
    shutil.rmtree(cache_path)
os.environ["PERU_CACHE_NAME"] = cache_path

r = Runtime()
r.verbose = True

parser = Parser(r.plugins)

scope = parser.parse_string("""
git module peru:
    url: https://github.com/oconnor663/peru.git

    imports:
        dotfiles.vimrc: module_vimrc_dir/

    rule license:
        imports:
            dotfiles.vimrc: rule_vimrc_dir/

        build: |
            mkdir out
            cp LICENSE out
            cp module_vimrc_dir/vimrc out/module_vimrc
            cp rule_vimrc_dir/vimrc out/rule_vimrc
        export: out

git module dotfiles:
    url: https://github.com/oconnor663/dotfiles.git

    rule vimrc:
        build: mkdir out; cp vimrc out
        export: out
""")

resolver = Resolver(scope, r.cache)

tree = resolver.get_tree("peru.license")
print("peru.license tree:", tree)

export_path = tempfile.mkdtemp()
print("export dir", export_path)
r.cache.export_tree(tree, export_path)

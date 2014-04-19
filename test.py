#! /usr/bin/python3

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__),
                             "third-party/PyYAML-3.10/lib3"))

from peru import runtime, module, rule

os.environ["PERU_CACHE_NAME"] = "/tmp/f1"

r = runtime.Runtime()
r.verbose = True

c = r.cache

m = module.Remote(r.plugins["git"],
                  {"url": "https://github.com/oconnor663/peru.git"},
                  "mygitremote")

t = m.get_tree(c)
print(t)

myrule = rule.Rule("funrule", {
    "build": "mkdir foo; cp LICENSE foo/bar",
    "export": "foo",
})

t2 = myrule.get_tree(c, t)
print(t2)

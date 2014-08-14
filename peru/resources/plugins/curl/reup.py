#! /usr/bin/env python3

import hashlib
import os
import urllib.request


url = os.environ['PERU_MODULE_URL']
sha1 = os.environ.get('PERU_MODULE_SHA1')

digest = hashlib.sha1()
with urllib.request.urlopen(url) as request:
    while True:
        buf = request.read(4096)
        if not buf:
            break
        digest.update(buf)

print('sha1:', digest.hexdigest())

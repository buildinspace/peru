#! /usr/bin/env python3

import hashlib
import os
import urllib.request

reup_output = os.environ['PERU_REUP_OUTPUT']

url = os.environ['PERU_MODULE_URL']
sha1 = os.environ['PERU_MODULE_SHA1']

digest = hashlib.sha1()
with urllib.request.urlopen(url) as request:
    while True:
        buf = request.read(4096)
        if not buf:
            break
        digest.update(buf)

with open(reup_output, 'w') as output_file:
    print('sha1:', digest.hexdigest(), file=output_file)

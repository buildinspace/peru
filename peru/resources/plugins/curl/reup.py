#! /usr/bin/env python3

import hashlib
import urllib.request

from peru.plugin_shared import parse_plugin_args


fields, _ = parse_plugin_args(
    required_fields={'url'},
    optional_fields={'sha1', 'filename'})
url = fields['url']
sha1 = fields.get('sha1')
filename = fields.get('filename')

digest = hashlib.sha1()
with urllib.request.urlopen(url) as request:
    while True:
        buf = request.read(4096)
        if not buf:
            break
        digest.update(buf)

print('sha1:', digest.hexdigest())

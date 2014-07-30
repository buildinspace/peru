#! /usr/bin/env python3

import hashlib
import os
import sys
import urllib.request

from peru.plugin_shared import parse_plugin_args

from curl_plugin_shared import get_request_filename


fields, dest, _ = parse_plugin_args(
    required_fields={'url'},
    optional_fields={'sha1', 'filename'})
url = fields['url']
sha1 = fields.get('sha1')
filename = fields.get('filename')

digest = hashlib.sha1()
with urllib.request.urlopen(url) as request:
    if filename is None:
        filename = get_request_filename(request)
    full_filepath = os.path.join(dest, filename)
    with open(full_filepath, 'wb') as outfile:
        while True:
            buf = request.read(4096)
            if not buf:
                break
            outfile.write(buf)
            digest.update(buf)

if sha1 and digest.hexdigest() != sha1:
    print('Bad checksum!\n     url: {}\nexpected: {}\n  actual: {}'
          .format(url, sha1, digest.hexdigest()), file=sys.stderr)
    sys.exit(1)

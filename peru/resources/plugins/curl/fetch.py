#! /usr/bin/env python3

import hashlib
import os
import sys
import urllib.request

from curl_plugin_shared import get_request_filename


url = os.environ['PERU_MODULE_URL']
sha1 = os.environ['PERU_MODULE_SHA1']
filename = os.environ['PERU_MODULE_FILENAME']

digest = hashlib.sha1()
with urllib.request.urlopen(url) as request:
    if not filename:
        filename = get_request_filename(request)
    full_filepath = os.path.join(os.environ['PERU_FETCH_DEST'], filename)
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

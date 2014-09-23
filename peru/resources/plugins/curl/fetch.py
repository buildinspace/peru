#! /usr/bin/env python3

import os
import sys
import urllib.request

import curl_plugin_shared


url = os.environ['PERU_MODULE_URL']
sha1 = os.environ['PERU_MODULE_SHA1']
filename = os.environ['PERU_MODULE_FILENAME']

with urllib.request.urlopen(url) as request:
    if not filename:
        filename = curl_plugin_shared.get_request_filename(request)
    full_filepath = os.path.join(os.environ['PERU_FETCH_DEST'], filename)
    with open(full_filepath, 'wb') as output_file:
        digest = curl_plugin_shared.download_file(request, output_file)

if sha1 and digest != sha1:
    print('Bad checksum!\n     url: {}\nexpected: {}\n  actual: {}'
          .format(url, sha1, digest), file=sys.stderr)
    sys.exit(1)

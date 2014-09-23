#! /usr/bin/env python3

import os
import urllib.request

import curl_plugin_shared

reup_output = os.environ['PERU_REUP_OUTPUT']

url = os.environ['PERU_MODULE_URL']
sha1 = os.environ['PERU_MODULE_SHA1']

with urllib.request.urlopen(url) as request:
    digest = curl_plugin_shared.download_file(request, None)

with open(reup_output, 'w') as output_file:
    print('sha1:', digest, file=output_file)

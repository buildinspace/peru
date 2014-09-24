#! /usr/bin/env python3

import os
import sys

from svn_plugin_shared import svn

output_file = os.environ['PERU_REUP_OUTPUT']
url = os.environ['PERU_MODULE_URL']


def remote_head_rev(url):
    info = svn('info', url, capture_output=True).split('\n')
    for item in info:
        if item.startswith('Revision: '):
            return item.split()[1]

    print('svn revision info not found', file=sys.stderr)
    sys.exit(1)

rev = remote_head_rev(url)
with open(output_file, 'w') as f:
    # Quote Subversion revisions to prevent integer intepretation.
    print('rev:', '"{}"'.format(rev), file=f)

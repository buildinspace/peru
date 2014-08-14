#! /usr/bin/env python3

import os
import sys

from svn_plugin_shared import svn


def remote_head_rev(url):
    info = svn('info', url).split('\n')
    for item in info:
        if item.startswith('Revision: '):
            return item.split()[1]

    print('svn revision info not found', file=sys.stderr)
    sys.exit(1)

# Quote Subversion revisions to prevent integer intepretation.
print('rev:', '"{}"'.format(remote_head_rev(os.environ['PERU_MODULE_URL'])))

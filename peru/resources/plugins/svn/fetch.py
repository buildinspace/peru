#! /usr/bin/env python3

import os

from svn_plugin_shared import svn


# Just fetch the target revision and strip the metadata.
# Plugin-level caching for Subversion is futile.
svn(
    'export',
    '--force',
    '--revision',
    os.environ.get('PERU_MODULE_REV') or 'HEAD',
    os.environ['PERU_MODULE_URL'],
    os.environ['PERU_FETCH_DEST'])

#! /usr/bin/env python3

from peru import plugin_shared

import svn_plugin_shared
from svn_plugin_shared import svn


fields, dest, _ = plugin_shared.parse_plugin_args(
    svn_plugin_shared.required_fields,
    svn_plugin_shared.optional_fields)
url, rev, reup = svn_plugin_shared.unpack_fields(fields)

# Just fetch the target revision and strip the metadata.
# Plugin-level caching for Subversion is futile.
svn('export', '--force', '--revision', rev, url, dest)

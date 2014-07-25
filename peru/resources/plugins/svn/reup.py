#! /usr/bin/env python3

from peru import plugin_shared

import svn_plugin_shared


fields, _ = plugin_shared.parse_plugin_args(
    svn_plugin_shared.required_fields,
    svn_plugin_shared.optional_fields)
url, rev, reup = svn_plugin_shared.unpack_fields(fields)

# Quote Subversion revisions to prevent integer intepretation.
print('rev:', '"{}"'.format(svn_plugin_shared.remote_head_rev(url)))

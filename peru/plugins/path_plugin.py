#! /usr/bin/env python3

import distutils.dir_util


def get_files_callback(runtime, fields, target, name):
    distutils.dir_util.copy_tree(fields["path"], target,
                                 preserve_symlinks=True)


def peru_plugin_main(*args, **kwargs):
    runtime = kwargs["runtime"]
    def callback(fields, target, name):
        return get_files_callback(runtime, fields, target, name)
    kwargs["register"](
        name="path",
        required_fields={"path"},
        optional_fields = set(),
        get_files_callback = callback,
    )

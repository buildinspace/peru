import distutils.dir_util


def get_files_callback(fields, target):
    distutils.dir_util.copy_tree(fields["path"], target,
                                 preserve_symlinks=True)


def peru_plugin_main(*args, **kwargs):
    kwargs["register"](
        name="local",
        required_fields={"path"},
        optional_fields = set(),
        get_files_callback = get_files_callback,
    )

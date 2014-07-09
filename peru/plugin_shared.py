import sys


def parse_plugin_args(required_fields, optional_fields):
    args = sys.argv[1:]
    all_fields = required_fields | optional_fields
    # Find the "--" splitter between plugin fields and the command args.
    splitter = 0
    while splitter < len(args):
        if args[splitter] == "--":
            break
        # Field names will never be "--", but values can be. Increment by 2 so
        # that we skip the field values.
        splitter += 2
    else:
        raise BadFieldsError('Never found "--" splitter.')
    # Plugin fields are everything before the --
    field_args = args[:splitter]
    # The command args are everything after the --
    command_args = args[splitter+1:]
    # Make sure every field name is paired with a value.
    if len(field_args) % 2 != 0:
        raise BadFieldsError("uneven plugin fields", args)
    # Parse the fields into a dict.
    fields_dict = {}
    for field_name, field_val in zip(field_args[0::2], field_args[1::2]):
        # Don't accept any unexpected field names.
        if field_name not in all_fields:
            raise BadFieldsError("unrecognized field name", field_name)
        fields_dict[field_name] = field_val
    # Make sure all required fields are present.
    if fields_dict.keys() & required_fields != required_fields:
        raise BadFieldsError("missing required fields", args)
    return tuple([fields_dict] + [arg for arg in command_args])


class BadFieldsError(RuntimeError):
    def __init__(self, *args):
        RuntimeError.__init__(self, *args)

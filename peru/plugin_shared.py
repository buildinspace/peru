import sys


def plugin_main(required_fields, optional_fields, fetch_fn, reup_fn):
    """Plugins are invoked like this:
        plugin FIELD VAL ... -- command ARG ...
    A plugin should parse out its fields, validate them, and then triage on
    the command."""

    fields, command, command_args = parse_plugin_args(
        required_fields, optional_fields)

    if command == "fetch":
        dest, cache_path = command_args
        fetch_fn(fields, dest, cache_path)
    elif command == "reup":
        cache_path, = command_args
        reup_fn(fields, cache_path)
    else:
        print("Unknown command: " + command, file=sys.stderr)
        sys.exit(1)


def parse_plugin_args(required_fields, optional_fields):
    args = sys.argv[1:]
    all_fields = required_fields | optional_fields
    splitter = args.index("--")
    # Plugin fields are everything before the --
    field_args = args[:splitter]
    # The command and its args are everything after the --
    command = args[splitter+1]
    command_args = args[splitter+2:]
    # Make sure every field name is paired with a value.
    assert len(field_args) % 2 == 0, str(field_args) + " isn't even length"
    # Parse the fields into a dict.
    fields_dict = {}
    for field_name, field_val in zip(field_args[0::2], field_args[1::2]):
        # Don't accept any unexpected field names.
        assert field_name in all_fields
        fields_dict[field_name] = field_val
    # Make sure all required fields are present.
    assert fields_dict.keys() & required_fields == required_fields
    return fields_dict, command, command_args

import sys


def plugin_main(required_fields, optional_fields, fetch_fn, reup_fn):
    args = sys.argv[1:]
    all_fields = required_fields | optional_fields
    splitter = args.index("--")
    field_args = args[:splitter]
    command = args[splitter+1]
    command_args = args[splitter+2:]
    assert len(field_args) % 2 == 0, str(field_args) + " isn't even length"
    fields_dict = {}
    i = 0
    while i < len(field_args):
        field_name = field_args[i]
        field_val = field_args[i+1]
        assert field_name in all_fields
        fields_dict[field_name] = field_val
        i += 2
    assert fields_dict.keys() & required_fields == required_fields

    if command == "fetch":
        dest, cache_path = command_args
        fetch_fn(fields_dict, dest, cache_path)
    elif command == "reup":
        cache_path, = command_args
        reup_fn(fields_dict, cache_path)
    else:
        print("Unknown command: " + command, file=sys.stderr)

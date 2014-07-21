import yaml


def set_module_field_in_file(yaml_file_path, module_name, field_name, new_val):
    with open(yaml_file_path) as f:
        yaml_text = f.read()
    new_yaml_text = set_module_field(yaml_text, module_name,
                                     field_name, new_val)
    with open(yaml_file_path, "w") as f:
        f.write(new_yaml_text)


def set_module_field(yaml_text, module_name, field_name, new_val):
    yaml_dict = _parse_yaml_text(yaml_text)
    bounds = _get_module_field_bounds(yaml_dict, module_name, field_name)
    quoted_val = _maybe_quote(new_val)
    if bounds:
        # field exists, modify it
        return yaml_text[:bounds[0]] + quoted_val + yaml_text[bounds[1]:]
    else:
        # field is new, hack it in
        return _append_module_field(yaml_text, yaml_dict, module_name,
                                    field_name, quoted_val)


def _maybe_quote(val):
    '''All of our values should be strings. Usually those can be passed in as
    bare words, but if they're parseable as an int or float we need to quote
    them.'''
    assert isinstance(val, str), 'We should never set non-string values.'
    needs_quoting = False
    try:
        int(val)
        needs_quoting = True
    except:
        pass
    try:
        float(val)
        needs_quoting = True
    except:
        pass
    if needs_quoting:
        return '"{}"'.format(val)
    else:
        return val


def _append_module_field(yaml_text, yaml_dict, module_name,
                         field_name, new_val):
    module_fields = yaml_dict[module_name]
    # use the last field to determine position and indentation
    assert len(module_fields) > 0, "There aren't any fields here!"
    last_key = module_fields.keys[-1]
    last_val = module_fields.vals[-1]
    indentation = " " * last_key.start_mark.column
    yaml_lines = yaml_text.split("\n")

    # We want to append the new field at the end of the module. Unfortunately,
    # the end_mark of a multi-line field is actually the first line of the next
    # toplevel dict. Check for this.
    if last_val.end_mark.column > 0:
        new_line_number = last_val.end_mark.line + 1
    else:
        new_line_number = last_val.end_mark.line
        # If the module ended with a line of whitespace, insert before that.
        prev_line = yaml_lines[new_line_number - 1]
        if prev_line == "" or prev_line.isspace():
            new_line_number -= 1

    new_line = "{}{}: {}".format(indentation, field_name, new_val)
    new_yaml_lines = (yaml_lines[:new_line_number] +
                      [new_line] +
                      yaml_lines[new_line_number:])
    return "\n".join(new_yaml_lines)


def _get_module_field_bounds(yaml_dict, module_name, field_name):
    module_fields = yaml_dict[module_name]
    if field_name not in module_fields:
        return None
    field_val = module_fields[field_name]
    return (field_val.start_mark.index, field_val.end_mark.index)


def _parse_yaml_text(yaml_text):
    events_list = list(yaml.parse(yaml_text))
    return _parse_events_list(events_list)


def _parse_events_list(events_list):
    event = events_list.pop(0)
    if (isinstance(event, yaml.StreamStartEvent) or
            isinstance(event, yaml.DocumentStartEvent)):
        ret = _parse_events_list(events_list)
        events_list.pop(-1)
        return ret
    elif (isinstance(event, yaml.ScalarEvent) or
          isinstance(event, yaml.AliasEvent) or
          isinstance(event, yaml.SequenceEndEvent) or
          isinstance(event, yaml.MappingEndEvent)):
        return event
    elif isinstance(event, yaml.SequenceStartEvent):
        contents = []
        while True:
            item = _parse_events_list(events_list)
            if isinstance(item, yaml.SequenceEndEvent):
                end_event = item
                return YamlList(event, end_event, contents)
            contents.append(item)
    elif isinstance(event, yaml.MappingStartEvent):
        keys = []
        vals = []
        while True:
            key = _parse_events_list(events_list)
            if isinstance(key, yaml.MappingEndEvent):
                end_event = key
                return YamlDict(event, end_event, keys, vals)
            keys.append(key)
            val = _parse_events_list(events_list)
            vals.append(val)
    else:
        raise RuntimeError("Unknown parse event type", event)


class YamlDict:
    def __init__(self, start_event, end_event, keys, vals):
        assert all(isinstance(key, yaml.ScalarEvent) for key in keys)
        assert len(keys) == len(vals)
        self.keys = keys
        self.key_map = {key.value: key for key in keys}
        self.vals = vals
        self.val_map = {key.value: val for key, val in zip(keys, vals)}
        self.start_event = start_event
        self.end_event = end_event
        self.start_mark = start_event.start_mark
        self.end_mark = end_event.end_mark

    def __contains__(self, key):
        return key in self.key_map

    def __getitem__(self, key):
        return self.val_map[key]

    def __iter__(self):
        return iter(self.key_map)

    def __len__(self):
        return len(self.keys)


class YamlList:
    def __init__(self, start_event, end_event, contents):
        self._contents = contents
        self.start_event = start_event
        self.end_event = end_event
        self.start_mark = start_event.start_mark
        self.end_mark = end_event.end_mark

    def __contains__(self, item):
        return item in self._contents

    def __getitem__(self, index):
        return self._contents[index]

    def __iter__(self):
        return iter(self._contents)

    def __len__(self):
        return len(self._contents)

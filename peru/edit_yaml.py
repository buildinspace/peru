import yaml


def get_module_field_bounds(yaml_dict, module_name, field_name):
    module_fields = yaml_dict[module_name]
    field_key = module_fields.key_map[field_name]
    field_val = module_fields[field_name]
    return (field_key.start_mark.index,
            field_val.end_mark.index)


def parse_yaml_file(path):
    with open(path) as f:
        yaml_str = f.read()
    events = list(yaml.parse(yaml_str))
    return parse_events(events)


def parse_events(events_list):
    event = events_list.pop(0)
    if (isinstance(event, yaml.StreamStartEvent) or
            isinstance(event, yaml.DocumentStartEvent)):
        ret = parse_events(events_list)
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
            item = parse_events(events_list)
            if isinstance(item, yaml.SequenceEndEvent):
                end_event = item
                return YamlList(event, end_event, contents)
            contents.append(item)
    elif isinstance(event, yaml.MappingStartEvent):
        keys = []
        vals = []
        while True:
            key = parse_events(events_list)
            if isinstance(key, yaml.MappingEndEvent):
                end_event = key
                return YamlDict(event, end_event, keys, vals)
            keys.append(key)
            val = parse_events(events_list)
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

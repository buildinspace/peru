import yaml


def get_field_bounds(parse_tree, toplevel_name, field_name):
    for toplevel_event in parse_tree:
        if toplevel_event.value == toplevel_name:
            inner_dict = parse_tree[toplevel_event]
            assert isinstance(inner_dict, dict)
            for field_event in inner_dict:
                if field_event.value == field_name:
                    val_event = inner_dict[field_event]
                    assert isinstance(val_event, yaml.ScalarEvent)
                    return (field_event.start_mark.index,
                            val_event.end_mark.index)
    raise RuntimeError("Failed to find field '{}'/'{}'".format(
        toplevel_name, field_name))


def build_parse_tree(path):
    with open(path) as f:
        yaml_str = f.read()
    events = list(yaml.parse(yaml_str))
    return parse_events(events)


def parse_events(events_list):
    event = events_list.pop(0)
    if (isinstance(event, yaml.StreamStartEvent) or
            isinstance(event, yaml.DocumentStartEvent)):
        return parse_events(events_list[1:-1])
    elif (isinstance(event, yaml.ScalarEvent) or
          isinstance(event, yaml.AliasEvent) or
          isinstance(event, yaml.SequenceEndEvent) or
          isinstance(event, yaml.MappingEndEvent)):
        return event
    elif isinstance(event, yaml.SequenceStartEvent):
        ret = []
        while True:
            item = parse_events(events_list)
            if isinstance(item, yaml.SequenceEndEvent):
                return ret
            ret.append(item)
    elif isinstance(event, yaml.MappingStartEvent):
        ret = {}
        while True:
            key = parse_events(events_list)
            if isinstance(key, yaml.MappingEndEvent):
                return ret
            assert isinstance(key, yaml.ScalarEvent)
            val = parse_events(events_list)
            ret[key] = val
    else:
        raise RuntimeError("Unknown parse event type", event)

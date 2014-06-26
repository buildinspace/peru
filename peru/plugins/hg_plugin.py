#! /usr/bin/env python3

from peru.plugin_shared import plugin_main


def do_fetch(fields, dest, cache_path):
    print('doing hg fetch')


def parse_fields(fields):
    return (fields["url"],
            fields.get("rev", "default"),
            fields.get("reup", "default"))

required_fields = {"url"}
optional_fields = {"rev", "reup"}

if __name__ == "__main__":
    plugin_main(required_fields, optional_fields, do_fetch, None)

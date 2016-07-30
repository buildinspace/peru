from contextlib import contextmanager
from textwrap import indent


class PrintableError(Exception):
    def __init__(self, message, *args, **kwargs):
        self.message = message.format(*args, **kwargs)

    def __str__(self):
        return self.message

    def add_context(self, context):
        # TODO: Something more structured?
        self.message = 'In {}:\n{}'.format(context, indent(self.message, '  '))


@contextmanager
def error_context(context):
    try:
        yield
    except PrintableError as e:
        e.add_context(context)
        raise

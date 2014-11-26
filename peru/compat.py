import os
import sys


def makedirs(path):
    '''os.makedirs() has an exist_ok param, but it still throws errors when the
    path exists with non-default permissions. This isn't fixed until 3.4.'''
    if not os.path.exists(path):
        os.makedirs(path)


def is_fancy_terminal():
    '''The Windows terminal does not support most of the fancy things we want
    to do with colors and formatting. This is a quick and dirty way to make
    sure we default to simple output on Windows.'''
    return sys.stdout.isatty() and os.name != 'nt'

import os
import sys


# In Python versions prior to 3.4, __file__ returns a relative path. This path
# is fixed at load time, so if the program later cd's (as we do in tests, at
# least) __file__ is no longer valid. As a workaround, compute the absolute
# path at load time.
MODULE_ROOT = os.path.abspath(os.path.dirname(__file__))


def makedirs(path):
    '''os.makedirs() has an exist_ok param, but it still throws errors when the
    path exists with non-default permissions. This isn't fixed until 3.4.
    Pathlib won't be getting an exist_ok param until 3.5.'''
    path = str(path)  # compatibility with pathlib
    if not os.path.exists(path):
        os.makedirs(path)


def is_fancy_terminal():
    '''The Windows terminal does not support most of the fancy things we want
    to do with colors and formatting. This is a quick and dirty way to make
    sure we default to simple output on Windows.'''
    return sys.stdout.isatty() and os.name != 'nt'

import os


def makedirs(path):
    '''os.makedirs() has an exist_ok param, but it still throws errors when the
    path exists with non-default permissions. This isn't fixed until 3.4.'''
    if not os.path.exists(path):
        os.makedirs(path)


def indent(string, indentation):
    '''textwrap.indent was introduced in 3.3.'''
    lines = string.split('\n')
    for i, line in enumerate(lines):
        if line and not line.isspace():
            lines[i] = indentation + line
    return '\n'.join(lines)

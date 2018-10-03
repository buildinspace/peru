from pathlib import PurePosixPath
import re

from .error import PrintableError

UNESCAPED_STAR_EXPR = (
    r'(?<!\\)'  # negative lookbehind assertion for more backslashes
    r'(?:\\\\)*'  # non-capturing group of an even number of backslashes
    r'\*'  # literal *
)


def contains_unescaped_stars(glob):
    return re.search(UNESCAPED_STAR_EXPR, glob) is not None


def unglobbed_prefix(glob):
    '''Returns all the path components, starting from the beginning, up to the
    first one with any kind of glob. So for example, if glob is 'a/b/c*/d',
    return 'a/b'.'''
    parts = []
    for part in PurePosixPath(glob).parts:
        if contains_unescaped_stars(part):
            break
        else:
            parts.append(part)
    return str(PurePosixPath(*parts)) if parts else ''


def _split_on_indices(s, indices):
    start = 0
    for i in indices:
        yield s[start:i]
        start = i + 1
    yield s[start:]


def split_on_stars_interpreting_backslashes(s):
    r'''We don't want to do in-place substitutions of a regex for *, because we
    need to be able to regex-escape the rest of the string. Instead, we split
    the string on *'s, so that the rest can be regex-escaped and then rejoined
    with the right regex. While we're doing this, check for backslash-escaped
    *'s and \'s, and leave them in as literals (to be regex-escaped in the next
    step).'''

    star_indices = [
        match.end() - 1 for match in re.finditer(UNESCAPED_STAR_EXPR, s)
    ]
    literalized_parts = [
        part.replace(r'\*', '*').replace(r'\\', '\\')
        for part in _split_on_indices(s, star_indices)
    ]
    return literalized_parts


def glob_to_path_regex(glob):
    '''Supports * and **. Backslashes can escape stars or other backslashes. As
    in pathlib, ** may not adjoin any characters other than slash. Unlike
    pathlib, because we're not talking to the actual filesystem, ** will match
    files as well as directories. Paths get canonicalized before they're
    converted, so duplicate and trailing slashes get dropped. You should make
    sure the other paths you try to match are in canonical (Posix) form as
    well.'''

    canonical_glob = str(PurePosixPath(glob))

    # The final regex starts with ^ and ends with $ to force it to match the
    # whole path.
    regex = '^'
    components = canonical_glob.split('/')
    for i, component in enumerate(components):
        if component == '**':
            if i == len(components) - 1:
                raise GlobError(glob,
                                '** may not be the last component in a path.')
            else:
                regex += r'(?:[^/]+/)*'
        elif '**' in component:
            raise GlobError(glob, '** must be an entire path component.')
        else:
            if component == '*':
                # A lone * may not match empty.
                regex += r'[^/]+'
            else:
                # A * with other characters may match empty. Escape all other
                # regex special characters.
                star_parts = split_on_stars_interpreting_backslashes(component)
                escaped_parts = map(re.escape, star_parts)
                regex += r'[^/]*'.join(escaped_parts)
            # Add a trailing slash for every component except **.
            if i < len(components) - 1:
                regex += '/'

    regex += '$'
    return regex


class GlobError(PrintableError):
    def __init__(self, glob, message):
        new_message = 'Glob error in "{}": {}'.format(glob, message)
        super().__init__(new_message)

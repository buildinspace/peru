import collections
import re

import peru.glob as glob
import shared


class GlobTest(shared.PeruTest):
    def test_split_on_stars_interpreting_backslashes(self):
        cases = [
            ('', ['']),
            ('*', ['', '']),
            ('abc', ['abc']),
            ('abc\\', ['abc\\']),
            ('abc\\n', ['abc\\n']),
            ('abc\\\\', ['abc\\']),
            ('ab*c', ['ab', 'c']),
            ('*abc*', ['', 'abc', '']),
            (r'a\*bc', ['a*bc']),
            (r'a\\*bc', ['a\\', 'bc']),
            (r'a\\\*bc', ['a\\*bc']),
            (r'a\\\\*bc', ['a\\\\', 'bc']),
        ]
        for input, output in cases:
            self.assertEqual(
                output, glob.split_on_stars_interpreting_backslashes(input),
                'Failed split for input {}'.format(input))

    def test_glob_to_path_regex(self):
        Case = collections.namedtuple('Case', ['glob', 'matches', 'excludes'])
        cases = [
            Case(
                glob='a/b/c',
                matches=['a/b/c'],
                excludes=['a/b', 'a/b/c/', '/a/b/c', 'a/b/c/d']),
            # * should be able to match nothing.
            Case(
                glob='a/*b/c',
                matches=['a/b/c', 'a/xb/c'],
                excludes=['a/x/c', 'a/c', 'a//c']),
            # But * by itself should never match an empty path component.
            Case(
                glob='a/*/c',
                matches=['a/b/c', 'a/boooo/c', 'a/*/c'],
                excludes=['a/c', 'a/b/d/c', 'a//c']),
            # Similarly, ** does not match empty path components. It's tempting
            # to allow this, but we never want '**/c' to match '/c'.
            Case(
                glob='a/**/c',
                matches=['a/b/c', 'a/d/e/f/g/c', 'a/c'],
                excludes=['a/b/c/d', 'x/a/c', 'a//c']),
            Case(
                glob='a/**/**/c',
                matches=['a/b/c', 'a/d/e/f/g/c', 'a/c'],
                excludes=['a/b/c/d', 'x/a/c', 'a//c']),
            Case(glob='**/c', matches=['a/b/c', 'c'], excludes=['/c', 'c/d']),
            Case(
                glob='**/*/c', matches=['a/b/c', 'a/c'], excludes=['c', '/c']),
            # Leading slashes should be preserved if present.
            Case(glob='/a', matches=['/a'], excludes=['a']),
            Case(
                glob='/**/c',
                matches=['/a/b/c', '/c'],
                excludes=['c', 'a/b/c']),
            # Make sure special characters are escaped properly.
            Case(glob='a|b', matches=['a|b'], excludes=['a', 'b']),
            # Test escaped * characters.
            Case(glob='a\\*', matches=['a*'], excludes=['a', 'aa']),
        ]
        for case in cases:
            regex = glob.glob_to_path_regex(case.glob)
            for m in case.matches:
                assert re.match(regex, m), \
                    'Glob {} (regex: {} ) should match path {}'.format(
                        case.glob, regex, m)
            for e in case.excludes:
                assert not re.match(regex, e), \
                    'Glob {} (regex: {} ) should not match path {}'.format(
                    case.glob, regex, e)

    def test_bad_globs(self):
        bad_globs = [
            '**',
            'a/b/**',
            'a/b/**/',
            'a/b/**c/d',
        ]
        for bad_glob in bad_globs:
            with self.assertRaises(glob.GlobError):
                glob.glob_to_path_regex(bad_glob)

    def test_unglobbed_prefix(self):
        assert glob.unglobbed_prefix('a/b/c*/d') == 'a/b'
        assert glob.unglobbed_prefix('a/b/**/d') == 'a/b'
        assert glob.unglobbed_prefix('/a/b/*/d') == '/a/b'
        assert glob.unglobbed_prefix('*/a/b') == ''

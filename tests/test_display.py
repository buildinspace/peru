import io
import re
import textwrap

from peru import display
import shared


class DisplayTest(shared.PeruTest):
    def test_quiet_display(self):
        output = io.StringIO()
        disp = display.QuietDisplay(output)
        with disp.get_handle('title') as handle:
            handle.write('some stuff!')
        disp.print('other stuff?')
        self.assertEqual('other stuff?\n', output.getvalue())

    def test_verbose_display(self):
        output = io.StringIO()
        disp = display.VerboseDisplay(output)
        with disp.get_handle('title') as handle:
            handle.write('in job 1\n')
            disp.print('print stuff')
            handle.write('in job 2\n')
        expected = textwrap.dedent('''\
            === started title ===
            print stuff
            === finished title ===
            in job 1
            in job 2
            ===
            ''')
        self.assertEqual(expected, output.getvalue())

    def test_fancy_display(self):
        output = FakeTerminal()
        disp = display.FancyDisplay(output)

        handle1 = disp.get_handle('title1')
        handle1.__enter__()
        handle1.write('something1')
        disp._draw()
        # We need to test trailing spaces, and the '# noqa: W291' tag stops the
        # linter from complaining about these.
        expected1 = textwrap.dedent('''\
            ╶ title1: something1 
            ''')  # noqa: W291
        self.assertEqual(expected1, output.getlines())

        handle2 = disp.get_handle('title2')
        handle2.__enter__()
        handle2.write('something2')
        disp._draw()
        expected2 = textwrap.dedent('''\
            ┌ title1: something1 
            └ title2: something2 
            ''')  # noqa: W291
        self.assertEqual(expected2, output.getlines())

        handle3 = disp.get_handle('title3')
        handle3.__enter__()
        handle3.write('something3')
        disp._draw()
        expected3 = textwrap.dedent('''\
            ┌ title1: something1 
            ├ title2: something2 
            └ title3: something3 
            ''')  # noqa: W291
        self.assertEqual(expected3, output.getlines())

        disp.print('stuff above')
        # Calling _draw() should not be necessary after print(). This ensures
        # that we won't lose output if the program exits before _draw_later()
        # gets another chance to fire.
        expected4 = textwrap.dedent('''\
            stuff above
            ┌ title1: something1 
            ├ title2: something2 
            └ title3: something3 
            ''')  # noqa: W291
        self.assertEqual(expected4, output.getlines())

        handle2.__exit__(None, None, None)
        disp._draw()
        expected5 = textwrap.dedent('''\
            stuff above
            ┌ title1: something1 
            └ title3: something3 
            ''')  # noqa: W291
        self.assertEqual(expected5, output.getlines())

        handle1.__exit__(None, None, None)
        disp._draw()
        expected6 = textwrap.dedent('''\
            stuff above
            ╶ title3: something3 
            ''')  # noqa: W291
        self.assertEqual(expected6, output.getlines())

        handle3.__exit__(None, None, None)
        # _draw() should not be necessary after the last job exits.
        expected7 = textwrap.dedent('''\
            stuff above
            ''')
        self.assertEqual(expected7, output.getlines())
        self.assertEqual(None, disp._draw_later_handle)


class FakeTerminal:
    '''Emulates a terminal by keeping track of a list of lines. Knows how to
    interpret the ANSI escape sequences that are used by FancyDisplay.'''

    def __init__(self):
        self.lines = [io.StringIO()]
        self.cursor_line = 0
        # Flush doesn't actually do anything in fake terminal, but we want to
        # make sure it gets called before any lines are read.
        self.flushed = False

    def write(self, string):
        tokens = [
            display.ANSI_DISABLE_LINE_WRAP, display.ANSI_ENABLE_LINE_WRAP,
            display.ANSI_CLEAR_LINE, display.ANSI_CURSOR_UP_ONE_LINE, '\n'
        ]
        # The parens make this a capturing expression, so the tokens will be
        # included in re.split()'s return list.
        token_expr = '(' + '|'.join(re.escape(token) for token in tokens) + ')'
        pieces = re.split(token_expr, string)

        for piece in pieces:
            if piece in (display.ANSI_DISABLE_LINE_WRAP,
                         display.ANSI_ENABLE_LINE_WRAP):
                # Ignore the line wrap codes. TODO: Test for these?
                continue
            elif piece == display.ANSI_CLEAR_LINE:
                buffer = self.lines[self.cursor_line]
                buffer.seek(0)
                buffer.truncate()
            elif piece == display.ANSI_CURSOR_UP_ONE_LINE:
                col = self.lines[self.cursor_line].tell()
                self.cursor_line -= 1
                assert self.cursor_line >= 0
                new_buffer = self.lines[self.cursor_line]
                new_buffer.seek(col)
            elif piece == '\n':
                self.cursor_line += 1
                if self.cursor_line == len(self.lines):
                    self.lines.append(io.StringIO())
                self.lines[self.cursor_line].seek(0)
            else:
                self.lines[self.cursor_line].write(piece)

    def flush(self):
        self.flushed = True

    def getlines(self):
        # Make sure flush() was called after the last write.
        assert self.flushed
        self.flushed = False
        # Make sure none of the lines at or beyond the cursor have any text.
        for i in range(self.cursor_line, len(self.lines)):
            assert self.lines[i].getvalue() == ''
        # Concatenate all the lines before the cursor, and append trailing
        # newlines.
        lines = io.StringIO()
        for i in range(self.cursor_line):
            lines.write(self.lines[i].getvalue())
            lines.write('\n')
        return lines.getvalue()

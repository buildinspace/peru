import io
import re
import sys

from . import async_helpers

# The display classes deal with output from subprocesses. The FancyDisplay
# gives a multi-line, real-time view of each running process that looks nice in
# the terminal. The VerboseDisplay collects output from each job and prints it
# all when the job is finished, in a way that's suitable for logs. The
# QuietDisplay prints nothing.
#
# All of the display types inherit from BaseDisplay and provide the same
# interface. Callers use get_handle() to get a display handle for each
# subprocess job that's going to run. The handle is used as a context manager
# (inside a with statement) to indicate when the job is starting and stopping,
# and all of the output from the subprocess is passed to the handle's write()
# method. There is also a print() method on the display, for output that's not
# tied to a particular job, which prints to the terminal in a way that won't
# get stomped on by FancyDisplay's redrawing.
#
# Like other errors, we handle job errors by throwing a PrintableError, which
# get caught in main. So the displays don't need to do anything special to show
# errors.

ANSI_CURSOR_UP_ONE_LINE = '\x1b[1A'
ANSI_CLEAR_LINE = '\x1b[2K'
ANSI_DISABLE_LINE_WRAP = '\x1b[?7l'
ANSI_ENABLE_LINE_WRAP = '\x1b[?7h'


class BaseDisplay:
    def __init__(self, output=None):
        self.output = output or sys.stdout
        # Every job/handle gets a unique id.
        self._next_job_id = 0
        # Output from each job is buffered.
        self.buffers = {}
        # Each job has a title, like the name of the module being fetched.
        self.titles = {}
        # We also keep track of any handles that haven't been entered yet, so
        # that the FancyDisplay can know when to finally clean up.
        self.outstanding_jobs = set()

    def get_handle(self, title):
        job_id = self._next_job_id
        self._next_job_id += 1
        self.titles[job_id] = title
        self.buffers[job_id] = io.StringIO()
        self.outstanding_jobs.add(job_id)
        return _DisplayHandle(self, job_id)

    # FancyDisplay overrides print() to avoid conflicting with redraws.
    def print(self, *args, **kwargs):
        print(*args, file=self.output, **kwargs)

    # Callbacks that get overridden by subclasses.

    def _job_started(self, job_id):
        pass

    def _job_written(self, job_id, string):
        pass

    def _job_finished(self, job_id):
        pass

    # Callbacks for handles.

    def _handle_start(self, job_id):
        self._job_started(job_id)

    def _handle_write(self, job_id, string):
        self.buffers[job_id].write(string)
        self._job_written(job_id, string)

    def _handle_finish(self, job_id):
        self.outstanding_jobs.remove(job_id)
        self._job_finished(job_id)


class QuietDisplay(BaseDisplay):
    '''Prints nothing.'''
    pass


class VerboseDisplay(BaseDisplay):
    '''Waits until jobs are finished and then prints all of their output at
    once, to make sure jobs don't get interleaved. We use '===' as a delimiter
    to try to separate jobs from one another, and from other output.'''

    def _job_started(self, job_id):
        print('===', 'started', self.titles[job_id], '===', file=self.output)

    def _job_finished(self, job_id):
        print('===', 'finished', self.titles[job_id], '===', file=self.output)
        outputstr = self.buffers[job_id].getvalue()
        if outputstr:
            self.output.write(outputstr)
            print('===', file=self.output)


class FancyDisplay(BaseDisplay):
    '''Prints a multi-line, real-time display of all the latest output lines
    from each job.'''

    def __init__(self, *args):
        super().__init__(*args)
        # Every time we draw we need to erase the lines that were printed
        # before. This keeps track of that number. Note that we split output on
        # newlines and use no-wrap control codes in the terminal, so we only
        # need to count the number of jobs drawn.
        self._lines_printed = 0
        # This is the list of all active jobs. There's no guarantee that jobs
        # start in any particular order, so this list also helps us keep the
        # order stable.
        self._job_slots = []
        # The last line output from each job. This is what gets drawn.
        self._output_lines = {}
        # Lines that need to be printed above the display. This has to happen
        # during the next draw, right after the display is cleared.
        self._to_print = []
        # To avoid flicker, we draw on a short timeout instead of every time we
        # receive output. When this asyncio handle is set, it means a draw is
        # already pending.
        self._draw_later_handle = None

    def print(self, *args, **kwargs):
        output = io.StringIO()
        print(*args, file=output, **kwargs)
        self._to_print.append(output.getvalue())
        # If we use _draw_later, the program might exit before the draw timer
        # fires. Drawing right now ensures that output never gets dropped.
        self._draw()

    def _draw(self):
        self._cancel_draw_later()

        # Erase everything we printed before.
        for i in range(self._lines_printed):
            self.output.write(ANSI_CURSOR_UP_ONE_LINE)
            self.output.write(ANSI_CLEAR_LINE)
        self._lines_printed = 0

        # If we have any lines from print(), print them now. They will end up
        # above the display like regular output.
        for string in self._to_print:
            self.output.write(string)
        self._to_print.clear()

        # Redraw all the jobs.
        self.output.write(ANSI_DISABLE_LINE_WRAP)
        for slot, job_id in enumerate(self._job_slots):
            # Fancy unicode box characters in the left column.
            if slot == 0:
                self.output.write('┌' if len(self._job_slots) > 1 else '╶')
            elif slot < len(self._job_slots) - 1:
                self.output.write('├')
            else:
                self.output.write('└')
            self.output.write(' ')
            self.output.write(self.titles[job_id])
            self.output.write(': ')
            self.output.write(self._output_lines[job_id])
            # Some terminals keep overwriting the last character in no-wrap
            # mode. Make the trailing character a space.
            self.output.write(' ')
            self.output.write('\n')
            self._lines_printed += 1
        self.output.write(ANSI_ENABLE_LINE_WRAP)

        # Finally, flush output to the terminal. Hopefully everything gets
        # painted in one frame.
        self.output.flush()

    def _draw_later(self):
        if self._draw_later_handle:
            # There is already a draw pending.
            return
        self._draw_later_handle = async_helpers.EVENT_LOOP.call_later(
            0.1, self._draw)

    def _cancel_draw_later(self):
        if self._draw_later_handle:
            self._draw_later_handle.cancel()
            self._draw_later_handle = None

    def _job_started(self, job_id):
        self._job_slots.append(job_id)
        self._output_lines[job_id] = ''
        self._draw_later()

    def _job_written(self, job_id, string):
        # We need to split output on newlines. Some programs (git) also use
        # carriage return to redraw a line, so we split on that too.
        any_newlines = '(?:\n|\r)+'  # (?: is non-capturing, for split()
        lines = [line.strip() for line in re.split(any_newlines, string)]

        # NB: We don't make any attempt here to join lines that might span
        # multiple write() calls. `create_subprocess_with_handle()` reads
        # output in 4096 byte chunks, so this isn't likely, but it's possible.
        for line in lines:
            # Ignore empty lines, both from the job and from re.split().
            if line:
                self._output_lines[job_id] = line
        self._draw_later()

    def _job_finished(self, job_id):
        self._job_slots.remove(job_id)
        if not self.outstanding_jobs:
            # If the last job is finished, the event loop might be about to
            # stop. Clear the terminal right now, because _draw_later might
            # never run.
            self._draw()
        else:
            # If there are pending jobs, don't clear the display immediately.
            # This avoids flickering between jobs when only one job is running
            # at a time (-j1).
            self._draw_later()


class _DisplayHandle:
    def __init__(self, display, job_id):
        self._display = display
        self._job_id = job_id
        self._opened = False
        self._closed = False

    def write(self, string):
        assert self._opened and not self._closed
        self._display._handle_write(self._job_id, string)

    # Context manager interface. We're extra careful to make sure that the
    # handle is only written to inside a with statment, and only used once.
    def __enter__(self):
        assert not self._opened and not self._closed
        self._opened = True
        self._display._handle_start(self._job_id)
        return self

    def __exit__(self, *args):
        assert self._opened and not self._closed
        self._display._handle_finish(self._job_id)
        self._job_id = None
        self._closed = True

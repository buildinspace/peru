import asyncio
import atexit
import codecs
import io
import os
import subprocess
import sys

from .error import PrintableError

# The default event loop on Windows doesn't support subprocesses, so we need to
# use the proactor loop. See:
# https://docs.python.org/3/library/asyncio-eventloops.html#available-event-loops
# Because the event loop is essentially a global variable, we have to set this
# at import time. Otherwise asyncio objects that get instantiated early
# (particularly Locks and Semaphores) could grab a reference to the wrong loop.
# TODO: Importing for side effects isn't very clean. Find a better way.
if os.name == 'nt':
    asyncio.set_event_loop(asyncio.ProactorEventLoop())

# We also need to make sure the event loop is explicitly closed, to avoid a bug
# in _UnixSelectorEventLoop.__del__. See http://bugs.python.org/issue23548.
atexit.register(asyncio.get_event_loop().close)


def run_task(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@asyncio.coroutine
def gather_coalescing_exceptions(coros, display, error_str):
    '''The tricky thing about running multiple coroutines in parallel is what
    we're supposed to do when one of them raises an exception. The approach
    we're using here is to catch all exceptions, print them, and keep waiting
    for all tasks to finish. Then after everything is done, if any exceptions
    were caught, we raise a new generic exception with the supplied message.

    Another minor detail: We also want to make sure to start coroutines in the
    order given, so that they end up appearing to the user alphabetically in
    the fancy display. Note that asyncio.gather() puts coroutines in a set
    internally, so we schedule coroutines *before* we give them to gather().
    '''

    @asyncio.coroutine
    def catching_logging_wrapper(coro):
        try:
            ret = yield from coro
            return (ret, None)
        except Exception as e:
            display.print(e)
            return (None, e)

    # Suppress a deprecation warning in Python 3.5, while continuing to support
    # 3.3 and early 3.4 releases.
    schedule = getattr(asyncio, 'ensure_future', getattr(asyncio, 'async'))

    futures = [schedule(catching_logging_wrapper(coro)) for coro in coros]

    result_pairs = yield from asyncio.gather(*futures)

    results = [pair[0] for pair in result_pairs]
    exceptions = [pair[1] for pair in result_pairs]

    if any(exceptions):
        raise GatherException(error_str)
    else:
        return results


class GatherException(PrintableError):
    pass


@asyncio.coroutine
def create_subprocess_with_handle(command, display_handle, *, shell=False, cwd,
                                  **kwargs):
    '''Writes subprocess output to a display handle as it comes in, and also
    returns a copy of it as a string. Throws if the subprocess returns an
    error. Note that cwd is a required keyword-only argument, on theory that
    peru should never start child processes "wherever I happen to be running
    right now."'''

    # We're going to get chunks of bytes from the subprocess, and it's possible
    # that one of those chunks ends in the middle of a unicode character. An
    # incremental decoder keeps those dangling bytes around until the next
    # chunk arrives, so that split characters get decoded properly. Use
    # stdout's encoding, but provide a default for the case where stdout has
    # been redirected to a StringIO. (This happens in tests.)
    encoding = sys.stdout.encoding or 'utf8'
    decoder_factory = codecs.getincrementaldecoder(encoding)
    decoder = decoder_factory(errors='replace')

    output_copy = io.StringIO()

    # Display handles are context managers. Entering and exiting the display
    # handle lets the display know when the job starts and stops.
    with display_handle:
        stdin = asyncio.subprocess.DEVNULL
        stdout = asyncio.subprocess.PIPE
        stderr = asyncio.subprocess.STDOUT
        if shell:
            proc = yield from asyncio.create_subprocess_shell(
                command, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd,
                **kwargs)
        else:
            proc = yield from asyncio.create_subprocess_exec(
                *command, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd,
                **kwargs)

        # Read all the output from the subprocess as its comes in.
        while True:
            outputbytes = yield from proc.stdout.read(4096)
            if not outputbytes:
                break
            outputstr = decoder.decode(outputbytes)
            outputstr_unified = _unify_newlines(outputstr)
            display_handle.write(outputstr_unified)
            output_copy.write(outputstr_unified)

        returncode = yield from proc.wait()

    if returncode != 0:
        raise subprocess.CalledProcessError(
            returncode, command, output_copy.getvalue())

    if hasattr(decoder, 'buffer'):
        # The utf8 decoder has this attribute, but some others don't.
        assert not decoder.buffer, 'decoder nonempty: ' + repr(decoder.buffer)

    return output_copy.getvalue()


def _unify_newlines(s):
    r'''Because all asyncio subprocess output is read in binary mode, we don't
    get universal newlines for free. But it's the right thing to do, because we
    do all our printing with strings in text mode, which translates "\n" back
    into the platform-appropriate line separator. So for example, "\r\n" in a
    string on Windows will become "\r\r\n" when it gets printed. This function
    ensures that all newlines are represented as "\n" internally, which solves
    that problem and also helps our tests work on Windows. Right now we only
    handle Windows, but we can expand this if there's ever another newline
    style we have to support.'''

    return s.replace('\r\n', '\n')


@asyncio.coroutine
def safe_communicate(process, input=None):
    '''Asyncio's communicate method has a bug where `communicate(input=b"")` is
    treated the same as `communicate(). That means that child processes can
    hang waiting for input, when their stdin should be closed. See
    https://bugs.python.org/issue26848. The issue is fixed upstream in
    https://github.com/python/asyncio/commit/915b6eaa30e1e3744e6f8223f996e197c1c9b91d,
    but we will probably always need this workaround for old versions.'''
    if input is not None and len(input) == 0:
        process.stdin.close()
        return (yield from process.communicate())
    else:
        return (yield from process.communicate(input))

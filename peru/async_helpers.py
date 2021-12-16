import asyncio
import atexit
import codecs
import contextlib
import io
import os
import subprocess
import sys
import traceback

from .error import PrintableError


# Prior to Python 3.8 (which switched to the ProactorEventLoop by default on
# Windows), the default event loop on Windows doesn't support subprocesses, so
# we need to use the proactor loop. See:
# https://docs.python.org/3/library/asyncio-eventloops.html#available-event-loops
# Because the event loop is essentially a global variable, we have to set this
# at import time. Otherwise asyncio objects that get instantiated early
# (particularly Locks and Semaphores) could grab a reference to the wrong loop.
# TODO: Importing for side effects isn't very clean. Find a better way.
if os.name == 'nt':
    EVENT_LOOP = asyncio.ProactorEventLoop()
else:
    EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

# We also need to make sure the event loop is explicitly closed, to avoid a bug
# in _UnixSelectorEventLoop.__del__. See http://bugs.python.org/issue23548.
atexit.register(EVENT_LOOP.close)


def run_task(coro):
    return EVENT_LOOP.run_until_complete(coro)


class GatheredExceptions(PrintableError):
    def __init__(self, exceptions, reprs):
        assert len(exceptions) > 0
        self.exceptions = []
        self.reprs = []
        for e, st in zip(exceptions, reprs):
            # Flatten in the exceptions list of any other GatheredExceptions we
            # see. (This happens, for example, if something throws inside a
            # recursive module.)
            if isinstance(e, GatheredExceptions):
                self.exceptions.extend(e.exceptions)
            else:
                self.exceptions.append(e)

            # Don't flatten the reprs. This would make us lose PrintableError
            # context. TODO: Represent context in a more structured way?
            self.reprs.append(st)

        self.message = "\n\n".join(self.reprs)


async def gather_coalescing_exceptions(coros, display, *, verbose):
    '''The tricky thing about running multiple coroutines in parallel is what
    we're supposed to do when one of them raises an exception. The approach
    we're using here is to catch exceptions and keep waiting for other tasks to
    finish. At the end, we reraise a GatheredExceptions error, if any
    exceptions were caught.

    Another minor detail: We also want to make sure to start coroutines in the
    order given, so that they end up appearing to the user alphabetically in
    the fancy display. Note that asyncio.gather() puts coroutines in a set
    internally, so we schedule coroutines *before* we give them to gather().
    '''

    exceptions = []
    reprs = []

    async def catching_wrapper(coro):
        try:
            return (await coro)
        except Exception as e:
            exceptions.append(e)
            if isinstance(e, PrintableError) and not verbose:
                reprs.append(e.message)
            else:
                reprs.append(traceback.format_exc())
            return None

    # Suppress a deprecation warning in Python 3.5, while continuing to support
    # 3.3 and early 3.4 releases.
    if hasattr(asyncio, 'ensure_future'):
        schedule = getattr(asyncio, 'ensure_future')
    else:
        schedule = getattr(asyncio, 'async')

    futures = [schedule(catching_wrapper(coro)) for coro in coros]

    results = await asyncio.gather(*futures)

    if exceptions:
        raise GatheredExceptions(exceptions, reprs)
    else:
        return results


async def create_subprocess_with_handle(command,
                                        display_handle,
                                        *,
                                        shell=False,
                                        cwd,
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
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                **kwargs)
        else:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                **kwargs)

        # Read all the output from the subprocess as its comes in.
        while True:
            outputbytes = await proc.stdout.read(4096)
            if not outputbytes:
                break
            outputstr = decoder.decode(outputbytes)
            outputstr_unified = _unify_newlines(outputstr)
            display_handle.write(outputstr_unified)
            output_copy.write(outputstr_unified)

        returncode = await proc.wait()

    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, command,
                                            output_copy.getvalue())

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


async def safe_communicate(process, input=None):
    '''Asyncio's communicate method has a bug where `communicate(input=b"")` is
    treated the same as `communicate(). That means that child processes can
    hang waiting for input, when their stdin should be closed. See
    https://bugs.python.org/issue26848. The issue is fixed upstream in
    https://github.com/python/asyncio/commit/915b6eaa30e1e3744e6f8223f996e197c1c9b91d,
    but we will probably always need this workaround for old versions.'''
    if input is not None and len(input) == 0:
        process.stdin.close()
        return (await process.communicate())
    else:
        return (await process.communicate(input))


class RaisesGatheredContainer:
    def __init__(self):
        self.exception = None


@contextlib.contextmanager
def raises_gathered(error_type):
    '''For use in tests. Many tests expect a single error to be thrown, and
    want it to be of a specific type. This is a helper method for when that
    type is inside a gathered exception.'''
    container = RaisesGatheredContainer()
    try:
        yield container
    except GatheredExceptions as e:
        # Make sure there is exactly one exception.
        if len(e.exceptions) != 1:
            raise
        inner = e.exceptions[0]
        # Make sure the exception is the right type.
        if not isinstance(inner, error_type):
            raise
        # Success.
        container.exception = inner

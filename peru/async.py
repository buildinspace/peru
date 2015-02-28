import asyncio
import atexit
import codecs
import io
import os
import subprocess
import sys

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


def stable_gather(*coros):
    '''asyncio.gather() starts tasks in a nondeterministic order (because it
    calls set() on its arguments). stable_gather starts the list of tasks in
    order, and passes the resulting futures to gather().

    As with gather(), stable_gather() isn't itself a coroutine, but it returns
    a future.'''
    assert len(coros) == len(set(coros)), 'no duplicates allowed'
    futures = [asyncio.async(coro) for coro in coros]
    return asyncio.gather(*futures)


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

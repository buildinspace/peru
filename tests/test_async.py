import asyncio
from asyncio.subprocess import PIPE
import sys

import peru.async
from shared import PeruTest, make_synchronous


class AsyncTest(PeruTest):

    @make_synchronous
    def test_safe_communicate(self):
        # Test safe_communicate with both empty and non-empty input.
        cat_command = [sys.executable, "-c",
                       "import sys; sys.stdout.write(sys.stdin.read())"]

        proc_empty = yield from asyncio.create_subprocess_exec(
            *cat_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = yield from peru.async.safe_communicate(proc_empty, b"")
        self.assertEqual(stdout, b"")

        proc_nonempty = yield from asyncio.create_subprocess_exec(
            *cat_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = yield from peru.async.safe_communicate(
            proc_nonempty, b"foo bar baz")
        self.assertEqual(stdout, b"foo bar baz")

        # And test a case with None input as well.
        true_command = [sys.executable, "-c", ""]
        proc_true = yield from asyncio.create_subprocess_exec(
            *true_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = yield from peru.async.safe_communicate(proc_true)
        self.assertEqual(stdout, b"")

import asyncio
from asyncio.subprocess import PIPE
import sys

from peru.async_helpers import safe_communicate
from shared import PeruTest, make_synchronous


class AsyncTest(PeruTest):
    @make_synchronous
    async def test_safe_communicate(self):
        # Test safe_communicate with both empty and non-empty input.
        cat_command = [
            sys.executable, "-c",
            "import sys; sys.stdout.write(sys.stdin.read())"
        ]

        proc_empty = await asyncio.create_subprocess_exec(
            *cat_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = await safe_communicate(proc_empty, b"")
        self.assertEqual(stdout, b"")

        proc_nonempty = await asyncio.create_subprocess_exec(
            *cat_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = await safe_communicate(proc_nonempty, b"foo bar baz")
        self.assertEqual(stdout, b"foo bar baz")

        # And test a case with None input as well.
        true_command = [sys.executable, "-c", ""]
        proc_true = await asyncio.create_subprocess_exec(
            *true_command, stdin=PIPE, stdout=PIPE)
        stdout, _ = await safe_communicate(proc_true)
        self.assertEqual(stdout, b"")

#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import asyncio
import threading

from noisidev import unittest
from . import threads


def func_success():
    return 'result'

def func_crash():
    raise RuntimeError


class ThreadsTest(unittest.AsyncTestCase):
    async def test_success(self):
        test_called = threading.Event()
        def test():
            test_called.set()
            return 'result'

        thread = threads.Thread(target=test, event_loop=self.loop)
        thread.start()
        result = await thread.join()

        self.assertTrue(test_called.is_set())
        self.assertEqual(result, 'result')

    async def test_raises_exception(self):
        thread = threads.Thread(target=func_crash, event_loop=self.loop)
        thread.start()

        with self.assertRaises(RuntimeError):
            await thread.join()

    async def test_timeout(self):
        stop_thread = threading.Event()
        def test():
            stop_thread.wait()

        thread = threads.Thread(target=test, event_loop=self.loop)
        thread.start()
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await thread.join(0.2)

        finally:
            stop_thread.set()
            await thread.join()

    async def test_done_cb(self):
        done_cb_called = asyncio.Event(loop=self.loop)
        async def done_cb():
            done_cb_called.set()

        thread = threads.Thread(target=func_success, event_loop=self.loop, done_cb=done_cb())
        thread.start()
        await thread.join()

        await done_cb_called.wait()

    async def test_done_cb_with_exception(self):
        done_cb_called = asyncio.Event(loop=self.loop)
        async def done_cb():
            done_cb_called.set()

        thread = threads.Thread(target=func_crash, event_loop=self.loop, done_cb=done_cb())
        thread.start()
        with self.assertRaises(RuntimeError):
            await thread.join()

        await done_cb_called.wait()

    async def test_done_cb_calls_join(self):
        done_cb_called = asyncio.Event(loop=self.loop)
        async def done_cb():
            result = await thread.join()
            self.assertEqual(result, 'result')
            done_cb_called.set()

        thread = threads.Thread(target=func_success, event_loop=self.loop, done_cb=done_cb())
        thread.start()

        await done_cb_called.wait()

    async def test_double_join(self):
        thread = threads.Thread(target=func_success, event_loop=self.loop)
        thread.start()
        result = await thread.join()
        self.assertEqual(result, 'result')
        result = await thread.join()
        self.assertEqual(result, 'result')

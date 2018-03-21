#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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
import logging

from noisidev import unittest
from . import backend_manager

logger = logging.getLogger(__name__)


class TestBackend(backend_manager.ManagedBackend):
    def __init__(self, event_loop):
        self.exception_in_start = False
        self.exception_in_stop = False
        self.num_restarts = 0
        self.is_restarted = asyncio.Event(loop=event_loop)
        self.is_stopped = asyncio.Event(loop=event_loop)

    async def cleanup(self):
        logger.info("Clean up backend...")

    async def start(self):
        logger.info("Starting backend...")
        if self.exception_in_start:
            raise RuntimeError("Start failed.")

    async def stop(self):
        logger.info("Stopping backend...")
        if self.exception_in_stop:
            raise RuntimeError("Stop failed.")

    async def started(self, mgr):
        logger.info("Backend started.")

    async def stopped(self, mgr):
        logger.info("Backend stopped.")
        self.is_stopped.set()
        if self.num_restarts > 0:
            self.num_restarts -= 1
            logger.info("Restarting...")
            mgr.start()
            await mgr.wait_until_running()
            self.is_restarted.set()


class BackendManagerTest(unittest.AsyncTestCase):
    def setup_testcase(self):
        self.backend = TestBackend(self.loop)
        self.mgr = backend_manager.BackendManager(self.loop, self.backend)

    async def test_success(self):
        self.assertFalse(self.mgr.is_running)

        self.mgr.start()
        await self.mgr.wait_until_running()
        self.assertTrue(self.mgr.is_running)

        self.mgr.stop()
        await self.mgr.wait_until_stopped()
        self.assertFalse(self.mgr.is_running)

    async def test_start_fails(self):
        self.backend.exception_in_start = True
        self.mgr.start()
        with self.assertRaises(RuntimeError):
            await self.mgr.wait_until_running()
        self.assertFalse(self.mgr.is_running)

    async def test_stop_fails(self):
        self.backend.exception_in_stop = True
        self.mgr.start()
        await self.mgr.wait_until_running()

        self.mgr.stop()
        with self.assertRaises(RuntimeError):
            await self.mgr.wait_until_stopped()

    async def test_crashed(self):
        self.mgr.start()
        await self.mgr.wait_until_running()
        self.mgr.crashed()
        await self.backend.is_stopped.wait()

    async def test_stop_crashed(self):
        self.mgr.start()
        await self.mgr.wait_until_running()
        self.mgr.crashed()
        self.mgr.stop()
        await self.mgr.wait_until_stopped()

    async def test_restart(self):
        self.backend.num_restarts = 1
        self.mgr.start()
        await self.mgr.wait_until_running()
        self.mgr.crashed()

        await self.backend.is_restarted.wait()

        self.mgr.stop()
        await self.mgr.wait_until_stopped()

    async def test_crash_and_stop_fails(self):
        error_handler_called = asyncio.Event(loop=self.loop)
        def error_handler(event_loop, context):
            error_handler_called.set()

        self.loop.set_exception_handler(error_handler)

        self.backend.exception_in_stop = True
        self.mgr.start()
        await self.mgr.wait_until_running()

        self.mgr.crashed()

        await error_handler_called.wait()

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

from noisidev import unittest
from noisicaa.constants import TEST_OPTS
from noisicaa.core import ipc

from . import process
from . import client


class TestClientImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client', socket_dir=TEST_OPTS.TMP_DIR)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(client.NodeDBClientMixin, TestClientImpl):
    pass


class NodeDBClientTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.process = None
        self.process_task = None
        self.client = None

    async def setup_testcase(self):
        self.process = process.NodeDBProcess(
            name='node_db', event_loop=self.loop, manager=None, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.process.setup()
        self.process_task = self.loop.create_task(
            self.process.run())

        self.client = TestClient(self.loop)
        await self.client.setup()
        await self.client.connect(self.process.server.address)

    async def cleanup_testcase(self):
        if self.client is not None:
            await self.client.disconnect(shutdown=True)
            await self.client.cleanup()
        if self.process is not None:
            if self.process_task is not None:
                await self.process.shutdown()
                await asyncio.wait_for(self.process_task, None, loop=self.loop)
            await self.process.cleanup()

    async def test_start_scan(self):
        pass  #await self.client.start_scan()

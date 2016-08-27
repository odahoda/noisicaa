#!/usr/bin/python3

import asyncio
import time
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa.core import ipc

from . import process
from . import client


class TestClientImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(client.NodeDBClientMixin, TestClientImpl):
    pass


class TestProcessImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'audioproc')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestProcess(process.NodeDBProcessMixin, TestProcessImpl):
    pass


class NodeDBClientTest(asynctest.TestCase):
    async def setUp(self):
        self.process = TestProcess(self.loop)
        await self.process.setup()
        self.process_task = self.loop.create_task(
            self.process.run())

        self.client = TestClient(self.loop)
        await self.client.setup()
        await self.client.connect(self.process.server.address)

    async def tearDown(self):
        await self.client.disconnect(shutdown=True)
        await self.client.cleanup()
        await asyncio.wait_for(self.process_task, None)
        await self.process.cleanup()

    async def test_start_scan(self):
        await self.client.start_scan()


if __name__ == '__main__':
    unittest.main()

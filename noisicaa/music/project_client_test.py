#!/usr/bin/python3

import asyncio
import time
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa.core import ipc

from . import project_process
from . import project_client


class TestClient(project_client.ProjectClientMixin):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await super().setup()
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestProjectProcessImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'project')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestProjectProcess(
        project_process.ProjectProcessMixin, TestProjectProcessImpl):
    pass


class ProxyTest(asynctest.TestCase):
    async def setUp(self):
        self.project_process = TestProjectProcess(self.loop)
        await self.project_process.setup()
        self.client = TestClient(self.loop)
        await self.client.setup()
        self.stub = await self.client.get_stub(
            self.project_process.server.address)

    async def tearDown(self):
        await self.stub.close()
        await self.client.cleanup()
        await self.project_process.cleanup()

    def test_root_proxy(self):
        proxy = self.stub.project
        self.assertEqual(proxy.current_sheet, 0)

    def test_fetch_proxy(self):
        proxy = self.stub.project.metadata
        self.assertIsNone(proxy.author)

    async def test_listener(self):
        callback_received = asyncio.Event()
        def callback(old, new):
            callback_received.set()
        listener = await self.stub.add_listener('/', 'current_sheet', callback)
        await self.stub.test()
        await callback_received.wait()
        await listener.remove()


if __name__ == '__main__':
    unittest.main()

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


class TestClientImpl():
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(project_client.ProjectClientMixin, TestClientImpl):
    pass


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
        await self.client.connect(self.project_process.server.address)

    async def tearDown(self):
        await self.client.shutdown()
        await self.client.disconnect()
        await self.client.cleanup()
        await self.project_process.cleanup()

    async def test_foo(self):
        project = self.client.project
        self.assertTrue(hasattr(project, 'current_sheet'))


if __name__ == '__main__':
    unittest.main()

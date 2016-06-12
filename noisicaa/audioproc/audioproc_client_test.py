#!/usr/bin/python3

import asyncio
import time
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa.core import ipc

from . import audioproc_process
from . import audioproc_client


class TestClient(audioproc_client.AudioProcClientMixin):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await super().setup()
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestAudioProcProcessImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'audioproc')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestAudioProcProcess(
        audioproc_process.AudioProcProcessMixin, TestAudioProcProcessImpl):
    pass


class ProxyTest(asynctest.TestCase):
    async def setUp(self):
        self.audioproc_process = TestAudioProcProcess(self.loop)
        await self.audioproc_process.setup()
        self.client = TestClient(self.loop)
        await self.client.setup()
        self.stub = await self.client.get_stub(
            self.audioproc_process.server.address)

    async def tearDown(self):
        await self.stub.end_session()
        await self.stub.shutdown()
        await self.stub.close()
        await self.client.cleanup()
        await self.audioproc_process.cleanup()

    async def test_foo(self):
        pass


if __name__ == '__main__':
    unittest.main()

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
from . import node_types


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
        await self.client.connect(self.audioproc_process.server.address)

    async def tearDown(self):
        await self.client.shutdown()
        await self.client.disconnect()
        await self.client.cleanup()
        await self.audioproc_process.cleanup()

    async def test_list_node_types(self):
        result = await self.client.list_node_types()
        self.assertTrue(
            all(isinstance(nt, node_types.NodeType) for nt in result),
            result)

    async def test_add_node(self):
        node_id = await self.client.add_node('whitenoise')
        self.assertIsInstance(node_id, str)

    async def test_remove_node(self):
        node_id = await self.client.add_node('whitenoise')
        await self.client.remove_node(node_id)

    async def test_connect_ports(self):
        node1_id = await self.client.add_node('whitenoise')
        node2_id = await self.client.add_node('nullsink')
        await self.client.connect_ports(node1_id, 'out', node2_id, 'in')

    async def test_disconnect_ports(self):
        node1_id = await self.client.add_node('whitenoise')
        node2_id = await self.client.add_node('nullsink')
        await self.client.connect_ports(node1_id, 'out', node2_id, 'in')
        await self.client.disconnect_ports(node1_id, 'out', node2_id, 'in')


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python3

import asyncio
import time
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa import node_db
from noisicaa.core import ipc

from . import audioproc_process
from . import audioproc_client


class TestClientImpl(object):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(audioproc_client.AudioProcClientMixin, TestClientImpl):
    pass


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
        self.passthru_description = node_db.ProcessorDescription(
            processor_name='null',
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        self.audioproc_process = TestAudioProcProcess(self.loop)
        await self.audioproc_process.setup()
        self.audioproc_task = self.loop.create_task(
            self.audioproc_process.run())
        self.client = TestClient(self.loop)
        await self.client.setup()
        await self.client.connect(self.audioproc_process.server.address)

    async def tearDown(self):
        await self.client.disconnect(shutdown=True)
        await self.client.cleanup()
        await asyncio.wait_for(self.audioproc_task, None)
        await self.audioproc_process.cleanup()

    async def test_add_remove_node(self):
        await self.client.add_node(id='test', description=self.passthru_description)
        await self.client.remove_node('test')

    async def test_connect_ports(self):
        await self.client.add_node(id='node1', description=self.passthru_description)
        await self.client.add_node(id='node2', description=self.passthru_description)
        await self.client.connect_ports('node1', 'out:left', 'node2', 'in:left')

    async def test_disconnect_ports(self):
        await self.client.add_node(id='node1', description=self.passthru_description)
        await self.client.add_node(id='node2', description=self.passthru_description)
        await self.client.connect_ports('node1', 'out:left', 'node2', 'in:left')
        await self.client.disconnect_ports('node1', 'out:left', 'node2', 'in:left')


if __name__ == '__main__':
    unittest.main()

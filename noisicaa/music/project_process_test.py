#!/usr/bin/python3

import asyncio
import time
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa.core import ipc

from . import project_process
from . import project_stub
from . import project_client


class ProjectProcessTest(asynctest.TestCase):
    async def setUp(self):
        self.server = ipc.Server(self.loop, 'client')
        await self.server.setup()

    async def tearDown(self):
        await self.server.cleanup()

    async def test_start_and_shutdown(self):
        async with core.ProcessManager(self.loop) as mgr:
            proc = await mgr.start_process(
                'project', project_process.ProjectProcess)
            async with project_stub.ProjectStub(self.loop, proc.address) as stub:
                await stub.start_session(self.server.address)
                await stub.ping()
                await stub.shutdown()
            await proc.wait()

    async def test_getprop(self):
        async with core.ProcessManager(self.loop) as mgr:
            proc = await mgr.start_process(
                'project', project_process.ProjectProcess)
            async with project_stub.ProjectStub(self.loop, proc.address) as stub:
                await stub.start_session(self.server.address)
                self.assertEqual(
                    await stub.get_property('/', 'current_sheet'), 0)
                await stub.shutdown()
            await proc.wait()

    async def test_add_listener(self):
        class Client(project_client.ProjectClientMixin):
            def __init__(self, event_loop):
                super().__init__()
                self.event_loop = event_loop
                self.server = ipc.Server(self.event_loop, 'client')

            async def setup(self):
                await super().setup()
                await self.server.setup()

        client = Client(self.loop)
        await client.setup()

        async with core.ProcessManager(self.loop) as mgr:
            proc = await mgr.start_process(
                'project', project_process.ProjectProcess)
            stub = await client.get_stub(proc.address)
            try:
                callback_received = asyncio.Event()
                def callback(old, new):
                    callback_received.set()
                listener = await stub.add_listener('/', 'current_sheet', callback)
                await stub.test()
                await callback_received.wait()
                await listener.remove()

            finally:
                await stub.shutdown()
                await stub.close()
                await proc.wait()


class ProxyTest(asynctest.TestCase):
    async def setUp(self):
        self.server = ipc.Server(self.loop, 'client')
        await self.server.setup()
        self.mgr = core.ProcessManager(self.loop)
        await self.mgr.setup()
        self.proc = await self.mgr.start_process(
            'project', project_process.ProjectProcess)
        self.stub = project_stub.ProjectStub(self.loop, self.proc.address)
        await self.stub.connect()
        await self.stub.start_session(self.server.address)

    async def tearDown(self):
        await self.stub.close()
        await self.mgr.cleanup()
        await self.server.cleanup()

    def test_root_proxy(self):
        proxy = self.stub.project
        self.assertEqual(proxy.current_sheet, 0)

    def test_fetch_proxy(self):
        proxy = self.stub.project.metadata
        self.assertIsNone(proxy.author)


if __name__ == '__main__':
    unittest.main()

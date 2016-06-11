#!/usr/bin/python3

import time
import unittest

import asynctest

from noisicaa import core
from noisicaa.core import ipc

from . import project_process
from . import project_stub


class ProjectProcessTest(asynctest.TestCase):
    async def test_start_and_shutdown(self):
        async with core.ProcessManager(self.loop) as mgr:
            proc = await mgr.start_process(
                'project', project_process.ProjectProcess)
            async with project_stub.ProjectStub(self.loop, proc.address) as stub:
                await stub.ping()
                await stub.shutdown()
            await proc.wait()

    async def test_getprop(self):
        async with core.ProcessManager(self.loop) as mgr:
            proc = await mgr.start_process(
                'project', project_process.ProjectProcess)
            async with project_stub.ProjectStub(self.loop, proc.address) as stub:
                self.assertEqual(
                    await stub.get_property('/', 'current_sheet'), 0)
                await stub.shutdown()
            await proc.wait()


class ProxyTest(asynctest.TestCase):
    async def setUp(self):
        self.mgr = core.ProcessManager(self.loop)
        await self.mgr.setup()
        self.proc = await self.mgr.start_process(
            'project', project_process.ProjectProcess)
        self.stub = project_stub.ProjectStub(self.loop, self.proc.address)
        await self.stub.connect()

    async def tearDown(self):
        await self.stub.close()
        await self.mgr.cleanup()

    def test_root_proxy(self):
        proxy = self.stub.project
        self.assertEqual(proxy.current_sheet, 0)

    def test_fetch_proxy(self):
        proxy = self.stub.project.metadata
        self.assertIsNone(proxy.author)


if __name__ == '__main__':
    unittest.main()

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
            async with project_client.ProjectStub(self.loop, proc.address) as stub:
                await stub.start_session(self.server.address)
                await stub.ping()
                await stub.shutdown()
            await proc.wait()


if __name__ == '__main__':
    unittest.main()

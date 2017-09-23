#!/usr/bin/python3

import asyncio
import time
import uuid
import unittest
from unittest import mock

import asynctest

from noisicaa import core
from noisicaa import node_db
from noisicaa.core import ipc
from noisicaa.ui import model

from . import project_process
from . import project_client
from . import project


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
    def __init__(self, event_loop, manager):
        super().__init__()
        self.event_loop = event_loop
        self.manager = manager
        self.server = ipc.Server(self.event_loop, 'project')

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestProjectProcess(
        project_process.ProjectProcessMixin, TestProjectProcessImpl):
    pass


class AsyncSetupBase():
    async def setup(self):
        pass

    async def cleanup(self):
        pass

class TestNodeDBProcess(node_db.NodeDBProcessBase, AsyncSetupBase):
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'node_db')

    async def setup(self):
        await super().setup()
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()
        await super().cleanup()

    def handle_start_session(self, client_address, flags):
        return '123'

    def handle_end_session(self, session_id):
        return None


class ProxyTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db_process = TestNodeDBProcess(self.loop)
        await self.node_db_process.setup()

        self.manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            self.assertEqual(cmd, 'CREATE_NODE_DB_PROCESS')
            return self.node_db_process.server.address
        self.manager.call.side_effect = mock_call

        self.project_process = TestProjectProcess(self.loop, self.manager)
        await self.project_process.setup()
        self.client = TestClient(self.loop)
        self.client.cls_map = model.cls_map
        await self.client.setup()
        await self.client.connect(self.project_process.server.address)

    async def tearDown(self):
        await self.client.shutdown()
        await self.client.disconnect()
        await self.client.cleanup()
        await self.project_process.cleanup()
        await self.node_db_process.cleanup()

    @unittest.skip("TODO: Requires a properly setup node_db")
    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertTrue(hasattr(project, 'current_sheet'))

    @unittest.skip("TODO: Requires a properly setup node_db")
    async def test_create_close_open(self):
        path = '/tmp/foo%s' % uuid.uuid4().hex
        await self.client.create(path)
        # TODO: set some property
        await self.client.close()
        await self.client.open(path)
        # TODO: check property
        await self.client.close()

    @unittest.skip("TODO: Requires a properly setup node_db")
    async def test_call_command(self):
        await self.client.create_inmemory()
        sheet = self.client.project.sheets[0]
        num_tracks = len(sheet.master_group.tracks)
        await self.client.send_command(
            sheet.id, 'AddTrack',
            track_type='score',
            parent_group_id=sheet.master_group.id)
        self.assertEqual(len(sheet.master_group.tracks), num_tracks + 1)


if __name__ == '__main__':
    unittest.main()

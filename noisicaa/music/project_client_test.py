#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import uuid
from unittest import mock

from noisidev import unittest
from noisicaa import node_db
from noisicaa.core import ipc
from noisicaa.ui import model

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


class AsyncSetupBase():
    async def setup(self):
        pass

    async def cleanup(self):
        pass

class TestNodeDBProcess(node_db.NodeDBProcessBase):
    def handle_start_session(self, client_address, flags):
        return '123'

    def handle_end_session(self, session_id):
        return None


class ProxyTest(unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.node_db_process = TestNodeDBProcess(
            name='node_db', event_loop=self.loop, manager=None)
        await self.node_db_process.setup()

        self.manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            self.assertEqual(cmd, 'CREATE_NODE_DB_PROCESS')
            return self.node_db_process.server.address
        self.manager.call.side_effect = mock_call

        self.project_process = project_process.ProjectProcess(
            name='project', manager=self.manager, event_loop=self.loop)
        await self.project_process.setup()

        self.client = TestClient(self.loop)
        self.client.cls_map = model.cls_map
        await self.client.setup()
        await self.client.connect(self.project_process.server.address)

    async def cleanup_testcase(self):
        await self.client.shutdown()
        await self.client.disconnect()
        await self.client.cleanup()
        await self.project_process.cleanup()
        await self.node_db_process.cleanup()

    @unittest.skip("TODO: Requires a properly setup node_db")
    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertTrue(hasattr(project, 'metadata'))

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
        project = self.client.project
        num_tracks = len(project.master_group.tracks)
        await self.client.send_command(
            project.id, 'AddTrack',
            track_type='score',
            parent_group_id=project.master_group.id)
        self.assertEqual(len(project.master_group.tracks), num_tracks + 1)

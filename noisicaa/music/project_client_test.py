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
from noisicaa.core import ipc
from noisicaa.ui import model
from noisicaa.constants import TEST_OPTS
from noisicaa.node_db import process as node_db_process

from . import project_process
from . import project_client


class TestClientImpl():
    def __init__(self, event_loop):
        super().__init__()
        self.event_loop = event_loop
        self.server = ipc.Server(self.event_loop, 'client', socket_dir=TEST_OPTS.TMP_DIR)

    async def setup(self):
        await self.server.setup()

    async def cleanup(self):
        await self.server.cleanup()


class TestClient(project_client.ProjectClientMixin, TestClientImpl):
    pass


class ProjectClientTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.node_db_process = None
        self.node_db_process_task = None
        self.project_process = None
        self.project_process_task = None
        self.client = None

    async def setup_testcase(self):
        self.node_db_process = node_db_process.NodeDBProcess(
            name='node_db', event_loop=self.loop, manager=None, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.node_db_process.setup()
        self.node_db_process_task = self.loop.create_task(self.node_db_process.run())

        self.manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            self.assertEqual(cmd, 'CREATE_NODE_DB_PROCESS')
            return self.node_db_process.server.address
        self.manager.call.side_effect = mock_call

        self.project_process = project_process.ProjectProcess(
            name='project', manager=self.manager, event_loop=self.loop, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.project_process.setup()
        self.project_process_task = self.loop.create_task(self.project_process.run())

        self.client = TestClient(self.loop)
        self.client.cls_map = model.cls_map
        await self.client.setup()
        await self.client.connect(self.project_process.server.address)

    async def cleanup_testcase(self):
        if self.client is not None:
            await self.client.disconnect()
            await self.client.cleanup()

        if self.project_process is not None:
            if self.project_process_task is not None:
                await self.project_process.shutdown()
                self.project_process_task.cancel()
            await self.project_process.cleanup()

        if self.node_db_process is not None:
            if self.node_db_process_task is not None:
                await self.node_db_process.shutdown()
                self.node_db_process_task.cancel()
            await self.node_db_process.cleanup()

    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertTrue(hasattr(project, 'metadata'))

    async def test_create_close_open(self):
        path = '/tmp/foo%s' % uuid.uuid4().hex
        await self.client.create(path)
        # TODO: set some property
        await self.client.close()
        await self.client.open(path)
        # TODO: check property
        await self.client.close()

    async def test_call_command(self):
        await self.client.create_inmemory()
        project = self.client.project
        num_tracks = len(project.master_group.tracks)
        await self.client.send_command(
            project.id, 'AddTrack',
            track_type='score',
            parent_group_id=project.master_group.id)
        self.assertEqual(len(project.master_group.tracks), num_tracks + 1)

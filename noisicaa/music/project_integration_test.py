#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import copy
import logging
import os.path
import uuid
from typing import Dict, Tuple

import async_generator
from google.protobuf import message as protobuf

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import model
from noisicaa import editor_main_pb2
from noisicaa.model import model_base_pb2
from . import project_client
from . import project_client_model
from . import commands_pb2

logger = logging.getLogger(__name__)


class ProjectIntegrationTest(
        unittest_mixins.ServerMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.project = None  # type: project_client_model.Project
        self.pool = None  # type: model.Pool

    async def setup_testcase(self):
        self.setup_node_db_process(inline=True)
        self.setup_urid_mapper_process(inline=True)
        self.setup_writer_process(inline=True)
        self.setup_project_process(inline=True)

    def create_pool_snapshot(self, pool):
        snapshot = {}  # type: Dict[int, model_base_pb2.ObjectBase]
        for obj in pool.objects:
            assert obj.id not in snapshot
            snapshot[obj.id] = copy.deepcopy(obj.proto)
        return snapshot

    def assertSnapshotsEqual(self, s1, s2):
        diffs = []

        ids_not_in_1 = set(s2.keys()) - set(s1.keys())
        if ids_not_in_1:
            diffs.append("Objects missing in s1:")
            for obj_id in sorted(ids_not_in_1):
                diffs.append(str(s2[obj_id]))

        ids_not_in_2 = set(s1.keys()) - set(s2.keys())
        if ids_not_in_2:
            diffs.append("Objects missing in s2:")
            for obj_id in sorted(ids_not_in_2):
                diffs.append(str(s1[obj_id]))

        for obj_id in sorted(set(s1.keys()) & set(s2.keys())):
            f1 = {
                desc.name: (desc, value)
                for desc, value in s1[obj_id].ListFields()
            }
            f2 = {
                desc.name: (desc, value)
                for desc, value in s2[obj_id].ListFields()
            }

            has_diff = False
            for field in set(f1.keys()) | set(f2.keys()):
                _, value1 = f1.get(field, (None, None))
                if isinstance(value1, protobuf.Message) and not value1.ListFields():
                    value1 = None
                _, value2 = f2.get(field, (None, None))
                if isinstance(value2, protobuf.Message) and not value2.ListFields():
                    value2 = None

                if value1 != value2:
                    has_diff = True

            if has_diff:
                diffs.append(
                    "Objects differ:\n=== s1:\n%s\n=== s2:\n%s" % (s1[obj_id], s2[obj_id]))

        if diffs:
            self.fail('\n'.join(diffs))

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_client(self, create_process=True, process_address=None, shutdown=True):
        if create_process:
            create_project_process_request = editor_main_pb2.CreateProjectProcessRequest(
                uri='test-project')
            create_project_process_response = editor_main_pb2.CreateProcessResponse()
            await self.process_manager_client.call(
                'CREATE_PROJECT_PROCESS',
                create_project_process_request, create_project_process_response)
            process_address = create_project_process_response.address

        client = project_client.ProjectClient(
            event_loop=self.loop, server=self.server)
        try:
            await client.setup()
            await client.connect(process_address)

            await async_generator.yield_(client)
        finally:
            await client.disconnect()
            await client.cleanup()

            if shutdown:
                await self.process_manager_client.call(
                    'SHUTDOWN_PROCESS',
                    editor_main_pb2.ShutdownProcessRequest(
                        address=process_address))

    async def create_project(
            self, client) -> Tuple[project_client_model.Project, project_client.Pool, str]:
        path = os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)
        await client.create(path)
        project = client.project
        return project, project._pool, path

    async def open_project(
            self, client, path) -> Tuple[project_client_model.Project, project_client.Pool]:
        await client.open(path)
        project = client.project
        return project, project._pool

    async def send_command(self, client, pool, **kwargs):
        snapshot_before = self.create_pool_snapshot(pool)

        cmd = commands_pb2.Command(**kwargs)
        result = await client.send_command(cmd)
        snapshot_after = self.create_pool_snapshot(pool)

        # Undo and redo this command, and check that project states remain correct.
        await client.undo()
        self.assertSnapshotsEqual(self.create_pool_snapshot(pool), snapshot_before)
        await client.redo()
        self.assertSnapshotsEqual(self.create_pool_snapshot(pool), snapshot_after)

        return result

    async def test_script1(self):
        # Create a new process, connect to it and create a blank project.
        async with self.create_client() as client:
            _, pool, path = await self.create_project(client)
            #snapshot_blank = self.create_pool_snapshot(pool)

            # Create track1 (ScoreTrack)
            #insert_index =
            await self.send_command(
                client, pool,
                command='create_node',
                create_node=commands_pb2.CreateNode(
                    uri='builtin://score-track'))
            #track1 = project.master_group.tracks[insert_index]

            # Disconnect from and shutdown process, without calling close().
            snapshot_before_disconnect = self.create_pool_snapshot(pool)

        async with self.create_client() as client:
            _, pool = await self.open_project(client, path)
            self.assertSnapshotsEqual(self.create_pool_snapshot(pool), snapshot_before_disconnect)

            await client.close()

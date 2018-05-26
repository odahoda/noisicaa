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

import fractions
import logging
import os.path
import uuid
from typing import Dict  # pylint: disable=unused-import

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.core import ipc
from noisicaa.constants import TEST_OPTS
from . import project_client
from . import render_settings_pb2
from . import commands_pb2

logger = logging.getLogger(__name__)


class ProjectClientTestBase(unittest_mixins.ProcessManagerMixin, unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = None

    async def setup_testcase(self):
        self.setup_node_db_process(inline=True)
        self.setup_project_process(inline=True)
        await self.connect_project_client()

    def get_project_path(self):
        return os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)

    async def connect_project_client(self):
        if self.client is not None:
            await self.client.disconnect(shutdown=True)
            await self.client.cleanup()

        project_address = await self.process_manager_client.call(
            'CREATE_PROJECT_PROCESS', 'test-project')

        self.client = project_client.ProjectClient(
            event_loop=self.loop, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.client.setup()
        await self.client.connect(project_address)

    async def cleanup_testcase(self):
        if self.client is not None:
            await self.client.disconnect(shutdown=True)
            await self.client.cleanup()


class ProjectClientTest(ProjectClientTestBase):
    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertIsInstance(project.metadata, project_client.Metadata)

    async def test_create_close_open(self):
        path = self.get_project_path()
        await self.client.create(path)
        # TODO: set some property
        await self.client.close()

        await self.connect_project_client()
        await self.client.open(path)
        # TODO: check property
        await self.client.close()

    async def test_call_command(self):
        await self.client.create_inmemory()
        project = self.client.project
        num_tracks = len(project.master_group.tracks)
        await self.client.send_command(commands_pb2.Command(
            target=project.id,
            add_track=commands_pb2.AddTrack(
                track_type='score',
                parent_group_id=project.master_group.id)))
        self.assertEqual(len(project.master_group.tracks), num_tracks + 1)


class RenderTest(ProjectClientTestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cb_server = None
        self.current_state = None
        self.current_progress = fractions.Fraction(0)
        self.bytes_received = 0

        self.handle_state = self._handle_state
        self.handle_progress = self._handle_progress
        self.handle_data = self._handle_data

    def _handle_state(self, state):
        self.assertIsInstance(state, str)
        self.assertNotEqual(state, self.current_state)
        self.current_state = state

    def _handle_progress(self, progress):
        self.assertEqual(self.current_state, 'render')
        self.assertIsInstance(progress, fractions.Fraction)
        self.assertGreaterEqual(progress, self.current_progress)
        self.current_progress = progress
        return False

    def _handle_data(self, data):
        self.assertIsInstance(data, bytes)
        self.bytes_received += len(data)
        return True, ''

    async def setup_testcase(self):
        self.setup_urid_mapper_process(inline=True)
        self.setup_audioproc_process(inline=True)

        await self.client.create_inmemory()

        # pylint: disable=unnecessary-lambda
        self.cb_server = ipc.Server(self.loop, 'render_cb', socket_dir=TEST_OPTS.TMP_DIR)
        self.cb_server.add_command_handler('STATE', lambda *a: self.handle_state(*a))
        self.cb_server.add_command_handler('PROGRESS', lambda *a: self.handle_progress(*a))
        self.cb_server.add_command_handler(
            'DATA', lambda *a: self.handle_data(*a), log_level=logging.DEBUG)
        await self.cb_server.setup()

    async def cleanup_testcase(self):
        if self.cb_server is not None:
            await self.cb_server.cleanup()

    async def test_success(self):
        header = bytearray()

        def handle_data(data):
            if len(header) < 4:
                header.extend(data)
            return self._handle_data(data)
        self.handle_data = handle_data

        await self.client.render(self.cb_server.address, render_settings_pb2.RenderSettings())

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_progress, fractions.Fraction(1))
        self.assertEqual(self.current_state, 'complete')
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(header[:4], b'fLaC')

    async def test_encoder_fails(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.FAIL__TEST_ONLY__

        await self.client.render(self.cb_server.address, settings)

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_state, 'failed')

    async def test_write_fails(self):
        def handle_data(data):
            self._handle_data(data)
            if self.bytes_received > 0:
                return False, "Disk full"
            return True, ""
        self.handle_data = handle_data

        await self.client.render(self.cb_server.address, render_settings_pb2.RenderSettings())

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_state, 'failed')
        self.assertGreater(self.bytes_received, 0)

    async def test_aborted(self):
        def handle_progress(progress):
            if progress > 0:
                return True
            return False
        self.handle_progress = handle_progress

        await self.client.render(self.cb_server.address, render_settings_pb2.RenderSettings())

        self.assertEqual(self.current_state, 'failed')

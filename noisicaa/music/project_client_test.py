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

# TODO: pylint-unclean

import fractions
import logging
import uuid
from unittest import mock
from typing import Dict  # pylint: disable=unused-import

from noisidev import unittest
from noisicaa.core import ipc
from noisicaa.ui import model
from noisicaa.constants import TEST_OPTS
from noisicaa.node_db import process as node_db_process
from noisicaa.audioproc import audioproc_process
from noisicaa.lv2 import urid_mapper_process
from . import project_process
from . import project_client
from . import render_settings_pb2

logger = logging.getLogger(__name__)


class ProjectClientTestBase(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.node_db_process = None
        self.node_db_process_task = None
        self.project_process = None
        self.project_process_task = None
        self.client = None
        self.manager_address_map = {}  # type: Dict[str, str]

    async def setup_testcase(self):
        self.manager = mock.Mock()
        async def mock_call(cmd, *args, **kwargs):
            return self.manager_address_map[cmd]
        self.manager.call.side_effect = mock_call

        self.node_db_process = node_db_process.NodeDBProcess(
            name='node_db', event_loop=self.loop, manager=self.manager, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.node_db_process.setup()
        self.node_db_process_task = self.loop.create_task(self.node_db_process.run())

        self.manager_address_map['CREATE_NODE_DB_PROCESS'] = self.node_db_process.server.address

        self.project_process = project_process.ProjectProcess(
            name='project', manager=self.manager, event_loop=self.loop, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.project_process.setup()
        self.project_process_task = self.loop.create_task(self.project_process.run())

        self.client = project_client.ProjectClient(event_loop=self.loop, tmp_dir=TEST_OPTS.TMP_DIR)
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


class ProjectClientTest(ProjectClientTestBase):
    @unittest.skip("TODO: reenable")
    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertTrue(hasattr(project, 'metadata'))

    @unittest.skip("TODO: reenable")
    async def test_create_close_open(self):
        path = '/tmp/foo%s' % uuid.uuid4().hex
        await self.client.create(path)
        # TODO: set some property
        await self.client.close()
        await self.client.open(path)
        # TODO: check property
        await self.client.close()

    @unittest.skip("TODO: reenable")
    async def test_call_command(self):
        await self.client.create_inmemory()
        project = self.client.project
        num_tracks = len(project.master_group.tracks)
        await self.client.send_command(
            project.id, 'AddTrack',
            track_type='score',
            parent_group_id=project.master_group.id)
        self.assertEqual(len(project.master_group.tracks), num_tracks + 1)


class RenderTest(ProjectClientTestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.urid_mapper_process = None
        self.urid_mapper_process_task = None
        self.audioproc_process = None
        self.audioproc_process_task = None

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
        await self.client.create_inmemory()

        self.urid_mapper_process = urid_mapper_process.URIDMapperProcess(
            name='urid_mapper', event_loop=self.loop, manager=self.manager, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.urid_mapper_process.setup()
        self.urid_mapper_process_task = self.loop.create_task(self.urid_mapper_process.run())

        self.manager_address_map['CREATE_URID_MAPPER_PROCESS'] = (
            self.urid_mapper_process.server.address)

        self.audioproc_process = audioproc_process.AudioProcProcess(
            name='audioproc', event_loop=self.loop, manager=self.manager, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.audioproc_process.setup()
        self.audioproc_process_task = self.loop.create_task(self.audioproc_process.run())

        self.manager_address_map['CREATE_AUDIOPROC_PROCESS'] = self.audioproc_process.server.address

        self.cb_server = ipc.Server(self.loop, 'render_cb', socket_dir=TEST_OPTS.TMP_DIR)
        self.cb_server.add_command_handler('STATE', lambda *a: self.handle_state(*a))
        self.cb_server.add_command_handler('PROGRESS', lambda *a: self.handle_progress(*a))
        self.cb_server.add_command_handler('DATA', lambda *a: self.handle_data(*a), log_level=logging.DEBUG)
        await self.cb_server.setup()

    async def cleanup_testcase(self):
        if self.cb_server is not None:
            await self.cb_server.cleanup()

        if self.audioproc_process is not None:
            if self.audioproc_process_task is not None:
                await self.audioproc_process.shutdown()
                self.audioproc_process_task.cancel()
            await self.audioproc_process.cleanup()

        if self.urid_mapper_process is not None:
            if self.urid_mapper_process_task is not None:
                await self.urid_mapper_process.shutdown()
                self.urid_mapper_process_task.cancel()
            await self.urid_mapper_process.cleanup()

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

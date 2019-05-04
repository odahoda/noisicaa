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

import fractions
import logging
import os.path
import uuid

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from noisicaa.constants import TEST_OPTS
from . import project_client
from . import render_pb2
from . import metadata

logger = logging.getLogger(__name__)


class ProjectClientTestBase(
        unittest_mixins.NodeDBMixin,
        unittest_mixins.URIDMapperMixin,
        unittest_mixins.ServerMixin,
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = None

    async def setup_testcase(self):
        self.setup_node_db_process(inline=True)
        self.setup_writer_process(inline=True)

        await self.create_project_client()

    def get_project_path(self):
        return os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)

    async def create_project_client(self):
        if self.client is not None:
            await self.client.cleanup()

        self.client = project_client.ProjectClient(
            event_loop=self.loop,
            server=self.server,
            tmp_dir=TEST_OPTS.TMP_DIR,
            manager=self.process_manager_client,
            node_db=self.node_db,
            urid_mapper=self.urid_mapper)
        await self.client.setup()

    async def cleanup_testcase(self):
        if self.client is not None:
            await self.client.cleanup()


class ProjectClientTest(ProjectClientTestBase):
    async def test_basic(self):
        await self.client.create_inmemory()
        project = self.client.project
        self.assertIsInstance(project.metadata, metadata.Metadata)

    async def test_create_close_open(self):
        path = self.get_project_path()
        await self.client.create(path)
        # TODO: set some property
        await self.client.close()

        await self.create_project_client()
        await self.client.open(path)
        # TODO: check property
        await self.client.close()

    async def test_call_command(self):
        await self.client.create_inmemory()
        project = self.client.project
        num_nodes = len(project.nodes)
        with project.apply_mutations():
            project.create_node('builtin://score-track')
        self.assertEqual(len(project.nodes), num_nodes + 1)


class RenderTest(ProjectClientTestBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cb_endpoint_address = None
        self.current_state = None
        self.current_progress = fractions.Fraction(0)
        self.bytes_received = 0

        self.handle_state = self._handle_state
        self.handle_progress = self._handle_progress
        self.handle_data = self._handle_data

    def _handle_state(self, request, response):
        self.assertNotEqual(request.state, self.current_state)
        self.current_state = request.state

    def _handle_progress(self, request, response):
        progress = fractions.Fraction(request.numerator, request.denominator)
        self.assertEqual(self.current_state, 'render')
        self.assertGreaterEqual(progress, self.current_progress)
        self.current_progress = progress
        response.abort = False

    def _handle_data(self, request, response):
        self.bytes_received += len(request.data)
        response.status = True

    async def setup_testcase(self):
        self.setup_audioproc_process(inline=True)

        await self.client.create_inmemory()

        # pylint: disable=unnecessary-lambda
        cb_endpoint = ipc.ServerEndpoint('render_cb')
        cb_endpoint.add_handler(
            'STATE', lambda request, response: self.handle_state(request, response),
            render_pb2.RenderStateRequest, empty_message_pb2.EmptyMessage)
        cb_endpoint.add_handler(
            'PROGRESS', lambda request, response: self.handle_progress(request, response),
            render_pb2.RenderProgressRequest, render_pb2.RenderProgressResponse)
        cb_endpoint.add_handler(
            'DATA', lambda request, response: self.handle_data(request, response),
            render_pb2.RenderDataRequest, render_pb2.RenderDataResponse)
        self.cb_endpoint_address = await self.server.add_endpoint(cb_endpoint)

    async def cleanup_testcase(self):
        if self.cb_endpoint_address is not None:
            await self.server.remove_endpoint('render_cb')

    async def test_success(self):
        header = bytearray()

        def handle_data(request, response):
            if len(header) < 4:
                header.extend(request.data)
            self._handle_data(request, response)
        self.handle_data = handle_data

        await self.client.render(self.cb_endpoint_address, render_pb2.RenderSettings())

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_progress, fractions.Fraction(1))
        self.assertEqual(self.current_state, 'complete')
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(header[:4], b'fLaC')

    async def test_encoder_fails(self):
        settings = render_pb2.RenderSettings()
        settings.output_format = render_pb2.RenderSettings.FAIL__TEST_ONLY__

        await self.client.render(self.cb_endpoint_address, settings)

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_state, 'failed')

    async def test_write_fails(self):
        def handle_data(request, response):
            self._handle_data(request, response)
            if self.bytes_received > 0:
                response.status = False
                response.msg = "Disk full"
                return
        self.handle_data = handle_data

        await self.client.render(self.cb_endpoint_address, render_pb2.RenderSettings())

        logger.info("Received %d encoded bytes", self.bytes_received)

        self.assertEqual(self.current_state, 'failed')
        self.assertGreater(self.bytes_received, 0)

    async def test_aborted(self):
        def handle_progress(request, response):
            progress = fractions.Fraction(request.numerator, request.denominator)
            response.abort = (progress > 0)
        self.handle_progress = handle_progress

        await self.client.render(self.cb_endpoint_address, render_pb2.RenderSettings())

        self.assertEqual(self.current_state, 'failed')

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

import logging
import os.path
import uuid

import async_generator

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa import editor_main_pb2
from noisicaa.constants import TEST_OPTS
from . import writer_client

logger = logging.getLogger(__name__)


class WriterClientTestBase(
        unittest_mixins.ProcessManagerMixin,
        unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.writer_address = None

    async def setup_testcase(self):
        self.setup_writer_process(inline=True)

        create_process_response = editor_main_pb2.CreateProcessResponse()
        await self.process_manager_client.call(
            'CREATE_WRITER_PROCESS',
            None, create_process_response)
        self.writer_address = create_process_response.address

    async def cleanup_testcase(self):
        if self.writer_address is not None:
            await self.process_manager_client.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.writer_address))

    def get_project_path(self):
        return os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def connect_client(self):
        client = writer_client.WriterClient(event_loop=self.loop)
        await client.setup()
        await client.connect(self.writer_address)
        try:
            await async_generator.yield_(client)
        finally:
            await client.disconnect()
            await client.cleanup()

    async def test_create_close_open(self):
        path = self.get_project_path()

        async with self.connect_client() as client:
            await client.create(path, b'initial_checkpoint')
            await client.close()

        async with self.connect_client() as client:
            checkpoint, actions = await client.open(path)
            self.assertEqual(checkpoint, b'initial_checkpoint')
            self.assertEqual(actions, [])
            await client.close()

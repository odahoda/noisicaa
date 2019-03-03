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

import typing
import logging
import os.path
import uuid

from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import model
from noisicaa import editor_main_pb2
from . import project_client

if typing.TYPE_CHECKING:
    from . import project_client_model

logger = logging.getLogger(__name__)


class CommandsTestMixin(
        unittest_mixins.ServerMixin,
        unittest_mixins.NodeDBMixin,
        unittest_mixins.ProcessManagerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.project_address = None  # type: str
        self.client = None  # type: project_client.ProjectClient
        self.project = None  # type: project_client_model.Project
        self.pool = None  # type: model.Pool

    async def setup_testcase(self):
        self.setup_node_db_process(inline=True)
        self.setup_project_process(inline=True)

        create_project_process_request = editor_main_pb2.CreateProjectProcessRequest(
            uri='test-project')
        create_project_process_response = editor_main_pb2.CreateProcessResponse()
        await self.process_manager_client.call(
            'CREATE_PROJECT_PROCESS',
            create_project_process_request, create_project_process_response)
        self.project_address = create_project_process_response.address

        self.client = project_client.ProjectClient(
            event_loop=self.loop, server=self.server, node_db=self.node_db)
        await self.client.setup()
        await self.client.connect(self.project_address)

        path = os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)
        await self.client.create(path)
        self.project = self.client.project
        self.pool = self.project._pool

        logger.info("Testcase setup complete")

    async def cleanup_testcase(self):
        logger.info("Testcase finished.")

        if self.client is not None:
            await self.client.close()
            await self.client.cleanup()

        if self.project_address is not None:
            await self.process_manager_client.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.project_address))

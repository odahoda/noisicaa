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

import logging
import os.path
import uuid

from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import model  # pylint: disable=unused-import
from . import project_client

logger = logging.getLogger(__name__)


class CommandsTestMixin(unittest_mixins.ProcessManagerMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = None  # type: project_client.ProjectClient
        self.project = None  # type: project_client.Project
        self.pool = None  # type: model.Pool

    async def setup_testcase(self):
        self.setup_node_db_process(inline=True)
        self.setup_project_process(inline=True)

        project_address = await self.process_manager_client.call(
            'CREATE_PROJECT_PROCESS', 'test-project')

        self.client = project_client.ProjectClient(
            event_loop=self.loop, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.client.setup()
        await self.client.connect(project_address)

        path = os.path.join(TEST_OPTS.TMP_DIR, 'test-project-%s' % uuid.uuid4().hex)
        await self.client.create(path)
        self.project = self.client.project
        self.pool = self.project._pool

        logger.info("Testcase setup complete")

    async def cleanup_testcase(self):
        logger.info("Testcase finished.")

        if self.client is not None:
            await self.client.close()
            await self.client.disconnect(shutdown=True)
            await self.client.cleanup()

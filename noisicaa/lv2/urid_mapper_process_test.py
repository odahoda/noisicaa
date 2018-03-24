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

# TODO: mypy-unclean

import logging

from noisidev import unittest
from noisicaa.constants import TEST_OPTS
from noisicaa import core
from noisicaa.core import ipc

logger = logging.getLogger(__name__)


class PluginUIProcessTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mgr = None
        self.cb_server = None
        self.uris = {}

    async def setup_testcase(self):
        self.mgr = core.ProcessManager(event_loop=self.loop)
        await self.mgr.setup()

        self.cb_server = ipc.Server(self.loop, 'urid_cb', TEST_OPTS.TMP_DIR)
        self.cb_server.add_command_handler('NEW_URIS', self.handle_new_uris)
        await self.cb_server.setup()

    async def cleanup_testcase(self):
        if self.cb_server is not None:
            await self.cb_server.cleanup()

        if self.mgr is not None:
            await self.mgr.cleanup()

    def handle_new_uris(self, uris):
        self.uris.update(uris)

    async def create_process(self):
        proc = await self.mgr.start_subprocess(
            'test-urid-mapper', 'noisicaa.lv2.urid_mapper_process.URIDMapperSubprocess')

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect()
        return stub

    async def test_foo(self):
        stub = await self.create_process()
        try:
            session_id = await stub.call('START_SESSION', self.cb_server.address)

            urid = await stub.call('MAP', 'http://www.odahoda.de/')
            self.assertIsInstance(urid, int)
            self.assertIn('http://www.odahoda.de/', self.uris)

            await stub.call('END_SESSION', session_id)

        finally:
            await stub.call('SHUTDOWN')
            await stub.close()

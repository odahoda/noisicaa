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
from typing import Dict

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa import core
from noisicaa.core import empty_message_pb2
from noisicaa.core import ipc
from . import urid_mapper_pb2

logger = logging.getLogger(__name__)


class PluginUIProcessTest(unittest_mixins.ServerMixin, unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mgr = None
        self.cb_endpoint_address = None
        self.uris = {}  # type: Dict[str, int]

    async def setup_testcase(self):
        self.mgr = core.ProcessManager(event_loop=self.loop)
        await self.mgr.setup()

        cb_endpoint = ipc.ServerEndpoint('urid_cb')
        cb_endpoint.add_handler(
            'NEW_URIS', self.handle_new_uris,
            urid_mapper_pb2.NewURIsRequest, empty_message_pb2.EmptyMessage)
        self.cb_endpoint_address = await self.server.add_endpoint(cb_endpoint)

    async def cleanup_testcase(self):
        if self.cb_endpoint_address is not None:
            await self.server.remove_endpoint('urid_cb')

        if self.mgr is not None:
            await self.mgr.cleanup()

    def handle_new_uris(self, request, response):
        for mapping in request.mappings:
            self.uris[mapping.uri] = mapping.urid

    async def create_process(self):
        proc = await self.mgr.start_subprocess(
            'test-urid-mapper', 'noisicaa.lv2.urid_mapper_process.URIDMapperSubprocess')

        stub = ipc.Stub(self.loop, proc.address)
        await stub.connect(core.StartSessionRequest(
            callback_address=self.cb_endpoint_address))
        return proc, stub

    async def test_map(self):
        proc, stub = await self.create_process()
        try:
            map_request = urid_mapper_pb2.MapRequest(uri='http://www.odahoda.de/')
            map_response = urid_mapper_pb2.MapResponse()
            await stub.call('MAP', map_request, map_response)
            self.assertGreater(map_response.urid, 0)
            self.assertIn('http://www.odahoda.de/', self.uris)

        finally:
            await stub.close()
            await proc.shutdown()

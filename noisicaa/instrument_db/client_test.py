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

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS

from . import process
from . import client


class InstrumentDBClientTest(unittest_mixins.ServerMixin, unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.process = None
        self.process_task = None
        self.client_server = None
        self.client = None

    async def setup_testcase(self):
        self.process = process.InstrumentDBProcess(
            name='instrument_db', event_loop=self.loop, manager=None, tmp_dir=TEST_OPTS.TMP_DIR)
        await self.process.setup()
        self.process_task = self.loop.create_task(self.process.run())

        self.client = client.InstrumentDBClient(self.loop, self.server)
        await self.client.setup()
        await self.client.connect(self.process.server.address)

    async def cleanup_testcase(self):
        if self.client is not None:
            await self.client.cleanup()

        if self.process is not None:
            if self.process_task is not None:
                await self.process.shutdown()
                await self.process_task
            await self.process.cleanup()

    async def test_start_scan(self):
        await self.client.start_scan()

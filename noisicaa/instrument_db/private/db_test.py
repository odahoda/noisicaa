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

import asyncio
import logging
import os.path

from noisidev import unittest
from noisicaa import constants
from noisicaa import instrument_db
from . import db

logger = logging.getLogger(__name__)


class InstrumentDBTest(unittest.AsyncTestCase):
    async def test_scan(self):
        complete = asyncio.Event(loop=self.loop)
        def state_listener(state):
            if state.state == instrument_db.ScanState.COMPLETED:
                complete.set()
            logger.info("state=%s", state)

        instdb = db.InstrumentDB(self.loop, '/tmp')
        instdb.scan_state_handlers.add(state_listener)
        try:
            instdb.setup()

            instdb.start_scan([os.path.join(constants.ROOT, '..', 'testdata')], False)
            self.assertTrue(await complete.wait())

        finally:
            instdb.cleanup()

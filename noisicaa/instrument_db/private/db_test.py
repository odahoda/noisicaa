#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import threading
import time
import unittest

import asynctest

from noisicaa import constants
from . import db

logger = logging.getLogger(__name__)


class NodeDBTest(asynctest.TestCase):
    async def test_foo(self):
        complete = asyncio.Event()
        def state_listener(state, *args):
            if state == 'complete':
                complete.set()
            logger.info("state=%s args=%s", state, args)

        instdb = db.InstrumentDB(self.loop, '/tmp')
        instdb.listeners.add('scan-state', state_listener)
        try:
            instdb.setup()

            instdb.start_scan([os.path.join(constants.ROOT, '..', 'testdata')], False)
            self.assertTrue(await complete.wait())

        finally:
            instdb.cleanup()


if __name__ == '__main__':
    unittest.main()

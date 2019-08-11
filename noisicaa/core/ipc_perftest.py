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
import random

from . import ipc_test_pb2
from . import ipc_test

logger = logging.getLogger(__name__)


class IPCPerfTest(ipc_test.IPCPerfTestBase):
    async def test_small_messages(self):
        request = ipc_test_pb2.TestRequest()
        request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 5000)

    async def test_large_messages(self):
        request = ipc_test_pb2.TestRequest()
        for _ in range(10000):
            request.t.add(numerator=random.randint(0, 4), denominator=random.randint(1, 2))
        await self.run_test(request, 100)

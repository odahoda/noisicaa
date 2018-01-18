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

import unittest

import asynctest


skip = unittest.skip


class TestCase(unittest.TestCase):
    def setUp(self):
        try:
            self.setup_testcase()
        except:
            self.cleanup_testcase()
            raise

    def tearDown(self):
        self.cleanup_testcase()

    def setup_testcase(self):
        pass

    def cleanup_testcase(self):
        pass


class AsyncTestCase(asynctest.TestCase):
    async def setUp(self):
        try:
            await self.setup_testcase()
        except:
            await self.cleanup_testcase()
            raise

    async def tearDown(self):
        await self.cleanup_testcase()

    async def setup_testcase(self):
        pass

    async def cleanup_testcase(self):
        pass


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

import asyncio
import logging

import async_generator

from noisidev import unittest
from noisidev import unittest_engine_mixins
from . import engine as engine_lib
from . import realm

logger = logging.getLogger(__name__)


class EngineTest(unittest_engine_mixins.HostSystemMixin, unittest.AsyncTestCase):

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_engine(self, *, backend='null'):
        engine = engine_lib.PyEngine(
            host_system=self.host_system, event_loop=self.loop, manager=None, server_address=None)
        try:
            await engine.setup()
            await engine.create_realm(name='root', parent=None)
            await engine.set_backend(backend)

            await async_generator.yield_(engine)

        finally:
            await engine.cleanup()

    async def test_engine_thread(self):
        async with self.create_engine():
            # TODO: wait for thread processing (listen for some notification).
            await asyncio.sleep(1, loop=self.loop)

    async def test_set_host_parameters(self):
        self.host_system.set_block_size(1024)
        async with self.create_engine() as engine:
            await engine.set_host_parameters(block_size=2048)

            # TODO: verify that the right things happened...

    async def test_create_realms(self):
        async with self.create_engine() as engine:
            root = engine.get_realm('root')
            self.assertIsInstance(root, realm.PyRealm)
            self.assertIsNone(root.parent)

            child = await engine.create_realm(name='child', parent='root')
            self.assertIs(engine.get_realm('child'), child)
            self.assertIs(child.parent, root)

            # No duplicates
            with self.assertRaises(engine_lib.DuplicateRealmName):
                await engine.create_realm(name='child', parent='root')

            grandchild = await engine.create_realm(name='grandchild', parent='child')
            self.assertIs(grandchild.parent, child)

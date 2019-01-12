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
from noisicaa.constants import TEST_OPTS
from . import ipc


class IPCTest(unittest.AsyncTestCase):
    async def test_ping(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()
                await stub.ping()
                await stub.ping()

            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()

    async def test_command(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            server.add_command_handler('foo', lambda: None)
            server.add_command_handler('bar', lambda: 'yo')
            server.add_command_handler('gnurz', lambda a: a + 1)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertIsNone(await stub.call('foo'))
                self.assertEqual(await stub.call('bar'), 'yo')
                self.assertEqual(await stub.call('gnurz', 3), 4)

    async def test_remote_exception(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            server.add_command_handler('foo', lambda: 1/0)
            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')

    async def test_async_handler(self):
        async with ipc.Server(self.loop, name='test', socket_dir=TEST_OPTS.TMP_DIR) as server:
            async def handler(arg):
                return arg + 1
            server.add_command_handler('foo', handler)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertEqual(await stub.call('foo', 3), 4)

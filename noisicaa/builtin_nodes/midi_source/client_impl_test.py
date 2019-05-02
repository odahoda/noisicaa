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

from typing import cast

from noisidev import unittest
from noisicaa.music import commands_test
from noisicaa import music
from . import server_impl
from . import commands


class MidiSourceTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> server_impl.MidiSource:
        await self.client.send_command(music.create_node(
            'builtin://midi-source'))
        return cast(server_impl.MidiSource, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, server_impl.MidiSource)

    async def test_set_device_uri(self):
        node = await self._add_node()

        await self.client.send_command(commands.update(
            node, set_device_uri='blabla'))
        self.assertEqual(node.device_uri, 'blabla')

    async def test_set_channel_filter(self):
        node = await self._add_node()

        await self.client.send_command(commands.update(
            node, set_channel_filter=2))
        self.assertEqual(node.channel_filter, 2)

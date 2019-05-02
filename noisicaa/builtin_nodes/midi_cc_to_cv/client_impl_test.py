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


class MidiCCtoCVTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> server_impl.MidiCCtoCV:
        await self.client.send_command(music.create_node(
            'builtin://midi-cc-to-cv'))
        return cast(server_impl.MidiCCtoCV, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, server_impl.MidiCCtoCV)

    async def test_create_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        await self.client.send_command(commands.create_channel(
            node, index=0))
        self.assertIs(node.channels[1], old_channel)
        self.assertEqual(len(node.channels), 2)

    async def test_delete_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        await self.client.send_command(commands.create_channel(
            node, index=0))
        await self.client.send_command(commands.delete_channel(
            node.channels[0]))
        self.assertEqual(len(node.channels), 1)
        self.assertIs(node.channels[0], old_channel)

    async def test_channel_set_midi_channel(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_midi_channel=12))
        self.assertEqual(channel.midi_channel, 12)

    async def test_channel_set_midi_controller(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_midi_controller=63))
        self.assertEqual(channel.midi_controller, 63)

    async def test_channel_set_min_value(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_min_value=440))
        self.assertEqual(channel.min_value, 440)

    async def test_channel_set_max_value(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_max_value=440))
        self.assertEqual(channel.max_value, 440)

    async def test_channel_set_log_scale(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_log_scale=True))
        self.assertTrue(channel.log_scale)

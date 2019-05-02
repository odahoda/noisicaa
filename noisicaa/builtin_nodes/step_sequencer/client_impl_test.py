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
from . import model_pb2
from . import server_impl
from . import commands


class StepSequencerTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> server_impl.StepSequencer:
        await self.client.send_command(music.create_node(
            'builtin://step-sequencer'))
        return cast(server_impl.StepSequencer, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, server_impl.StepSequencer)
        self.assertFalse(node.time_synched)
        self.assertEqual(len(node.channels), 1)
        self.assertEqual(len(node.channels[0].steps), node.num_steps)

    async def test_set_time_synched(self):
        node = await self._add_node()
        await self.client.send_command(commands.update(
            node, set_time_synched=True))
        self.assertTrue(node.time_synched)

    async def test_set_num_steps_increase(self):
        node = await self._add_node()
        await self.client.send_command(commands.update(
            node, set_num_steps=13))
        self.assertEqual(node.num_steps, 13)
        self.assertEqual(len(node.channels[0].steps), 13)

    async def test_set_num_steps_decrease(self):
        node = await self._add_node()
        await self.client.send_command(commands.update(
            node, set_num_steps=5))
        self.assertEqual(node.num_steps, 5)
        self.assertEqual(len(node.channels[0].steps), 5)

    async def test_add_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        await self.client.send_command(commands.update(
            node, add_channel=0))
        self.assertIs(node.channels[1], old_channel)
        self.assertEqual(len(node.channels), 2)
        self.assertEqual(len(node.channels[0].steps), node.num_steps)

    async def test_delete_channel(self):
        node = await self._add_node()
        old_channel = node.channels[0]
        await self.client.send_command(commands.update(
            node, add_channel=0))
        await self.client.send_command(commands.delete_channel(
            node.channels[0]))
        self.assertEqual(len(node.channels), 1)
        self.assertIs(node.channels[0], old_channel)

    async def test_channel_set_type(self):
        node = await self._add_node()
        channel = node.channels[0]
        await self.client.send_command(commands.update_channel(
            channel, set_type=model_pb2.StepSequencerChannel.GATE))
        self.assertEqual(channel.type, model_pb2.StepSequencerChannel.GATE)

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

    async def test_step_set_value(self):
        node = await self._add_node()
        step = node.channels[0].steps[0]
        await self.client.send_command(commands.update_step(
            step, set_value=1.0))
        self.assertEqual(step.value, 1.0)

    async def test_step_set_enabled(self):
        node = await self._add_node()
        step = node.channels[0].steps[0]
        await self.client.send_command(commands.update_step(
            step, set_enabled=True))
        self.assertTrue(step.enabled)

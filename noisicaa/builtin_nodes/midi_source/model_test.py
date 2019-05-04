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
from noisidev import unittest_mixins
from noisicaa.music import commands_test
from . import model
from . import processor_messages


class MidiSourceTest(
        unittest_mixins.NodeConnectorMixin,
        commands_test.CommandsTestMixin,
        unittest.AsyncTestCase):
    async def _add_node(self) -> model.MidiSource:
        with self.project.apply_mutations():
            return cast(
                model.MidiSource,
                self.project.create_node('builtin://midi-source'))

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.MidiSource)

    async def test_connector_init(self):
        node = await self._add_node()
        with self.connector(node) as initial_messages:
            self.assertEqual(
                initial_messages,
                [processor_messages.update(node.pipeline_node_id, '', -1)])

    async def test_set_device_uri(self):
        node = await self._add_node()
        with self.connector(node):
            with self.project.apply_mutations():
                node.device_uri = 'foo'
            self.assertEqual(
                self.messages,
                [processor_messages.update(node.pipeline_node_id, device_uri='foo')])

    async def test_set_channel_filter(self):
        node = await self._add_node()
        with self.connector(node):
            with self.project.apply_mutations():
                node.channel_filter = 2
            self.assertEqual(
                self.messages,
                [processor_messages.update(node.pipeline_node_id, channel_filter=2)])

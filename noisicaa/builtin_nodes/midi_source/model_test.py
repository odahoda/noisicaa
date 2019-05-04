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

from typing import cast, List

from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa import audioproc
from noisicaa.music import commands_test
from noisicaa.music import project
from noisicaa import music
from . import model
from . import commands
from . import processor_messages


class ConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()
        self.node = self.pool.create(model.MidiSource, name='test')
        self.messages = []  # type: List[audioproc.ProcessorMessage]

    def message_cb(self, msg):
        self.messages.append(msg)

    def test_messages_on_mutations(self):
        connector = self.node.create_node_connector(
            message_cb=self.message_cb, audioproc_client=None)
        try:
            self.assertEqual(
                connector.init(),
                [processor_messages.update(self.node.pipeline_node_id, '', -1)])

            self.messages.clear()
            self.node.device_uri = 'foo'
            self.assertEqual(
                self.messages,
                [processor_messages.update(self.node.pipeline_node_id, device_uri='foo')])

            self.messages.clear()
            self.node.channel_filter = 2
            self.assertEqual(
                self.messages,
                [processor_messages.update(self.node.pipeline_node_id, channel_filter=2)])

        finally:
            connector.close()


class MidiSourceTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> model.MidiSource:
        await self.client.send_command(music.create_node(
            'builtin://midi-source'))
        return cast(model.MidiSource, self.project.nodes[-1])

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, model.MidiSource)

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

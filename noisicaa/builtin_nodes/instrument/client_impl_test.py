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

from noisidev import unittest
from noisicaa.music import commands_test
from noisicaa import music
from . import client_impl
from . import commands


class InstrumentTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):

    async def _add_node(self) -> client_impl.Instrument:
        node_id = await self.client.send_command(music.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=music.AddPipelineGraphNode(
                uri='builtin://instrument')))
        return self.pool[node_id]

    async def test_add_node(self):
        node = await self._add_node()
        self.assertIsInstance(node, client_impl.Instrument)

    async def test_change_instrument_uri(self):
        node = await self._add_node()

        await self.client.send_command(commands.update_instrument(
            node.id, instrument_uri='blabla'))
        self.assertEqual(node.instrument_uri, 'blabla')

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
from typing import List

from noisidev import unittest
from noisicaa import audioproc
from noisicaa import model_base
from noisicaa import value_types
from . import commands_test
from . import project_client

logger = logging.getLogger(__name__)


class GraphCommandsTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):
    async def test_create_node(self):
        with self.project.apply_mutations():
            node = self.project.create_node(
                'builtin://midi-source',
                name='test_node')
        self.assertEqual(node.name, 'test_node')

    async def test_delete_node(self):
        with self.project.apply_mutations():
            node = self.project.create_node('builtin://midi-source')

        await self.client.send_command(project_client.delete_node(node))
        self.assertNotIn(node.id, [n.id for n in self.project.nodes])

    async def test_create_node_connection(self):
        with self.project.apply_mutations():
            node1 = self.project.create_node('builtin://midi-source')
            node2 = self.project.create_node('builtin://instrument')

        await self.client.send_command(project_client.create_node_connection(
            source_node=node1, source_port='out',
            dest_node=node2, dest_port='in'))
        conn = self.project.node_connections[-1]
        self.assertIs(conn.source_node, node1)
        self.assertEqual(conn.source_port, 'out')
        self.assertIs(conn.dest_node, node2)
        self.assertEqual(conn.dest_port, 'in')

    async def test_delete_node_connection(self):
        with self.project.apply_mutations():
            node1 = self.project.create_node('builtin://midi-source')
            node2 = self.project.create_node('builtin://instrument')
        await self.client.send_command(project_client.create_node_connection(
            source_node=node1, source_port='out',
            dest_node=node2, dest_port='in'))
        conn = self.project.node_connections[-1]

        await self.client.send_command(project_client.delete_node_connection(conn))
        self.assertNotIn(conn.id, [c.id for c in self.project.node_connections])

    async def test_set_graph_pos(self):
        with self.project.apply_mutations():
            node = self.project.create_node(
                'builtin://csound/reverb',
                graph_pos=value_types.Pos2F(200, 100))

        await self.client.send_command(project_client.update_node(
            node,
            set_graph_pos=value_types.Pos2F(100, 300)))
        self.assertEqual(node.graph_pos, value_types.Pos2F(100, 300))

    async def test_set_control_value(self):
        with self.project.apply_mutations():
            node = self.project.create_node('builtin://mixer')

        changes = []  # type: List[model_base.PropertyValueChange]
        node.control_value_map.init()
        node.control_value_map.control_value_changed.add('gain', changes.append)
        self.assertEqual(node.control_value_map.value('gain'), 0.0)

        await self.client.send_command(project_client.update_node(
            node,
            set_control_value=value_types.ControlValue(
                name='gain',
                value=1.0,
                generation=12)))

        self.assertEqual(node.control_value_map.value('gain'), 1.0)
        self.assertEqual(node.control_value_map.generation('gain'), 12)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].new_value, value_types.ControlValue('gain', 1.0, 12))

    async def test_set_plugin_state(self):
        with self.project.apply_mutations():
            node = self.project.create_node('builtin://csound/reverb')

        plugin_state = audioproc.PluginState(
            lv2=audioproc.PluginStateLV2(
                properties=[
                    audioproc.PluginStateLV2Property(
                        key='k1',
                        type='string',
                        value='lalila'.encode('utf-8'))]))
        await self.client.send_command(project_client.update_node(
            node,
            set_plugin_state=plugin_state))
        self.assertEqual(node.plugin_state, plugin_state)

    async def test_set_port_properties(self):
        with self.project.apply_mutations():
            node = self.project.create_node('builtin://csound/reverb')

        await self.client.send_command(project_client.update_node(
            node,
            set_port_properties=value_types.NodePortProperties('mix', exposed=True)))
        self.assertTrue(node.get_port_properties('mix').exposed)

        await self.client.send_command(project_client.update_node(
            node,
            set_port_properties=value_types.NodePortProperties('mix', exposed=False)))
        self.assertFalse(node.get_port_properties('mix').exposed)

        with self.assertRaises(Exception):
            await self.client.send_command(project_client.update_node(
                node,
                set_port_properties=value_types.NodePortProperties('holla')))

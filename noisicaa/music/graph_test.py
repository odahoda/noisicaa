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
from noisidev import unittest_mixins
from noisicaa import model_base
from noisicaa import value_types

logger = logging.getLogger(__name__)


class GraphCommandsTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):
    async def test_create_node(self):
        with self.project.apply_mutations('test'):
            node = self.project.create_node(
                'builtin://midi-source',
                name='test_node')
        self.assertEqual(node.name, 'test_node')

    async def test_delete_node(self):
        with self.project.apply_mutations('test'):
            node = self.project.create_node('builtin://midi-source')

        with self.project.apply_mutations('test'):
            self.project.remove_node(node)
        self.assertNotIn(node.id, [n.id for n in self.project.nodes])

    async def test_create_node_connection(self):
        with self.project.apply_mutations('test'):
            node1 = self.project.create_node('builtin://midi-source')
            node2 = self.project.create_node('builtin://instrument')

        with self.project.apply_mutations('test'):
            conn = self.project.create_node_connection(
                source_node=node1, source_port='out',
                dest_node=node2, dest_port='in')
        self.assertIs(conn.source_node, node1)
        self.assertEqual(conn.source_port, 'out')
        self.assertIs(conn.dest_node, node2)
        self.assertEqual(conn.dest_port, 'in')

    async def test_delete_node_connection(self):
        with self.project.apply_mutations('test'):
            node1 = self.project.create_node('builtin://midi-source')
            node2 = self.project.create_node('builtin://instrument')
            conn = self.project.create_node_connection(
                source_node=node1, source_port='out',
                dest_node=node2, dest_port='in')

        with self.project.apply_mutations('test'):
            self.project.remove_node_connection(conn)
        self.assertNotIn(conn.id, [c.id for c in self.project.node_connections])

    async def test_set_control_value(self):
        with self.project.apply_mutations('test'):
            node = self.project.create_node('builtin://mixer')

        changes = []  # type: List[model_base.PropertyValueChange]
        node.control_value_map.init()
        node.control_value_map.control_value_changed.add('gain', changes.append)
        self.assertEqual(node.control_value_map.value('gain'), 0.0)

        with self.project.apply_mutations('test'):
            node.set_control_value('gain', 1.0, 12)

        self.assertEqual(node.control_value_map.value('gain'), 1.0)
        self.assertEqual(node.control_value_map.generation('gain'), 12)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].new_value, value_types.ControlValue('gain', 1.0, 12))

    async def test_set_port_properties(self):
        with self.project.apply_mutations('test'):
            node = self.project.create_node('builtin://csound/reverb')

        with self.project.apply_mutations('test'):
            node.set_port_properties(
                value_types.NodePortProperties('mix', exposed=True))
        self.assertTrue(node.get_port_properties('mix').exposed)

        with self.project.apply_mutations('test'):
            node.set_port_properties(
                value_types.NodePortProperties('mix', exposed=False))
        self.assertFalse(node.get_port_properties('mix').exposed)

        with self.assertRaises(Exception):
            with self.project.apply_mutations('test'):
                node.set_port_properties(
                    value_types.NodePortProperties('holla'))

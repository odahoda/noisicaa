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

from noisidev import unittest
from noisicaa import audioproc
from noisicaa import model
from . import commands_pb2
from . import commands_test

logger = logging.getLogger(__name__)


class PipelineGraphTest(commands_test.CommandsTestMixin, unittest.AsyncTestCase):
    async def test_basic(self):
        audio_out = self.project.audio_out_node

        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]
        self.assertIs(node, self.project.pipeline_graph_nodes[node.index])

        conn1_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_connection',
            add_pipeline_graph_connection=commands_pb2.AddPipelineGraphConnection(
                source_node_id=node_id, source_port_name='out:left',
                dest_node_id=audio_out.id, dest_port_name='in:left')))
        conn1 = self.pool[conn1_id]
        self.assertIs(conn1, self.project.pipeline_graph_connections[conn1.index])

        conn2_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_connection',
            add_pipeline_graph_connection=commands_pb2.AddPipelineGraphConnection(
                source_node_id=node_id, source_port_name='out:right',
                dest_node_id=audio_out.id, dest_port_name='in:right')))
        conn2 = self.pool[conn2_id]
        self.assertIs(conn2, self.project.pipeline_graph_connections[conn2.index])

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='remove_pipeline_graph_connection',
            remove_pipeline_graph_connection=commands_pb2.RemovePipelineGraphConnection(
                connection_id=conn1.id)))
        self.assertNotIn(conn1, self.project.pipeline_graph_connections)
        self.assertIn(conn2, self.project.pipeline_graph_connections)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='remove_pipeline_graph_node',
            remove_pipeline_graph_node=commands_pb2.RemovePipelineGraphNode(
                node_id=node.id)))
        self.assertNotIn(node, self.project.pipeline_graph_nodes)

        self.assertNotIn(conn1, self.project.pipeline_graph_connections)
        self.assertNotIn(conn2, self.project.pipeline_graph_connections)

    async def test_change_graph_pos(self):
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]

        await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='change_pipeline_graph_node',
            change_pipeline_graph_node=commands_pb2.ChangePipelineGraphNode(
                graph_pos=model.Pos2F(100, 300).to_proto())))
        self.assertEqual(node.graph_pos, model.Pos2F(100, 300))

    async def test_set_pipeline_graph_control_value(self):
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]

        await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='set_pipeline_graph_control_value',
            set_pipeline_graph_control_value=commands_pb2.SetPipelineGraphControlValue(
                port_name='feedback',
                float_value=0.6,
                generation=12)))

    async def test_set_pipeline_graph_plugin_state(self):
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]

        plugin_state = audioproc.PluginState(
            lv2=audioproc.PluginStateLV2(
                properties=[
                    audioproc.PluginStateLV2Property(
                        key='k1',
                        type='string',
                        value='lalila'.encode('utf-8'))]))
        await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='set_pipeline_graph_plugin_state',
            set_pipeline_graph_plugin_state=commands_pb2.SetPipelineGraphPluginState(
                plugin_state=plugin_state)))
        self.assertEqual(node.plugin_state, plugin_state)

    @unittest.skip("Implementation broken")
    async def test_pipeline_graph_node_to_preset(self):
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]

        preset = await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='pipeline_graph_node_to_preset',
            pipeline_graph_node_to_preset=commands_pb2.PipelineGraphNodeToPreset()))
        self.assertIsInstance(preset, bytes)

    @unittest.skip("Implementation broken")
    async def test_pipeline_graph_node_from_preset(self):
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='add_pipeline_graph_node',
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri='builtin://csound/reverb',
                graph_pos=model.Pos2F(200, 100).to_proto())))
        node = self.pool[node_id]

        preset = await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='pipeline_graph_node_to_preset',
            pipeline_graph_node_to_preset=commands_pb2.PipelineGraphNodeToPreset()))

        await self.client.send_command(commands_pb2.Command(
            target=node.id,
            command='pipeline_graph_node_from_preset',
            pipeline_graph_node_from_preset=commands_pb2.PipelineGraphNodeFromPreset(
                preset=preset)))

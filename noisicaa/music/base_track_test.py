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

import logging
from typing import Type

from noisidev import unittest
from . import commands_pb2
from . import commands_test
from . import project_client

logger = logging.getLogger(__name__)


class TrackTestMixin(commands_test.CommandsTestMixin):
    node_uri = None  # type: str
    track_cls = None  # type: Type[project_client.Track]

    async def test_add_remove(self) -> None:
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri=self.node_uri)))
        node = self.pool[node_id]
        assert isinstance(node, self.track_cls)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            remove_pipeline_graph_node=commands_pb2.RemovePipelineGraphNode(
                node_id=node.id)))

    async def _add_track(self) -> project_client.Track:
        node_id = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_pipeline_graph_node=commands_pb2.AddPipelineGraphNode(
                uri=self.node_uri)))
        return self.pool[node_id]


class BaseTrackTest(TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://score_track'
    track_cls = project_client.ScoreTrack

    async def test_update_track_visible(self):
        track = await self._add_track()

        self.assertTrue(track.visible)
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track=commands_pb2.UpdateTrack(
                visible=False)))
        self.assertFalse(track.visible)

    async def test_update_track_list_position(self):
        track = await self._add_track()

        self.assertEqual(track.list_position, 0)
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track=commands_pb2.UpdateTrack(
                list_position=2)))
        self.assertEqual(track.list_position, 2)

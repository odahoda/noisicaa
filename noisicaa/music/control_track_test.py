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

from typing import List

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisicaa import audioproc
from . import project
from . import control_track
from . import commands_pb2
from . import project_client
from . import base_track_test


class ControlTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()

        self.project = demo_project.empty(self.pool, project.BaseProject, node_db=self.node_db)
        self.track = self.pool.create(control_track.ControlTrack, name='test')
        self.project.pipeline_graph_nodes.append(self.track)

        self.messages = []  # type: List[str]

    def message_cb(self, msg):
        self.assertEqual(int(msg.node_id, 16), self.track.id)
        # TODO: track the messages themselves and inspect their contents as well.
        self.messages.append(msg.WhichOneof('msg'))

    def test_messages_on_mutations(self):
        connector = self.track.create_node_connector(message_cb=self.message_cb)
        try:
            self.assertEqual(connector.init(), [])

            self.messages.clear()
            self.track.points.insert(
                0,
                self.pool.create(
                    control_track.ControlPoint, time=audioproc.MusicalTime(1, 4), value=0.5))
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point'])

            self.messages.clear()
            self.track.points.insert(
                1,
                self.pool.create(
                    control_track.ControlPoint, time=audioproc.MusicalTime(2, 4), value=0.8))
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point'])

            self.messages.clear()
            del self.track.points[0]
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point'])

            self.messages.clear()
            self.track.points[0].value = 0.2
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point',
                 'cvgenerator_add_control_point'])

            self.messages.clear()
            self.track.points[0].time = audioproc.MusicalTime(3, 4)
            self.assertEqual(
                self.messages,
                ['cvgenerator_remove_control_point',
                 'cvgenerator_add_control_point'])

        finally:
            connector.close()

    def test_messages_on_init(self):
        self.track.points.insert(
            0,
            self.pool.create(
                control_track.ControlPoint, time=audioproc.MusicalTime(1, 4), value=0.5))
        self.track.points.insert(
            1,
            self.pool.create(
                control_track.ControlPoint, time=audioproc.MusicalTime(2, 4), value=0.8))

        connector = self.track.create_node_connector(message_cb=self.message_cb)
        try:
            messages = connector.init()

            self.assertEqual(
                [msg.WhichOneof('msg') for msg in messages],
                ['cvgenerator_add_control_point',
                 'cvgenerator_add_control_point'])

        finally:
            connector.close()


class ControlTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://control_track'
    track_cls = project_client.ControlTrack

    async def test_add_control_point(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_control_point=commands_pb2.AddControlPoint(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                value=0.7)))
        self.assertEqual(track.points[0].time, audioproc.MusicalTime(1, 4))
        self.assertAlmostEqual(track.points[0].value, 0.7)

    async def test_remove_control_point(self):
        track = await self._add_track()
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_control_point=commands_pb2.AddControlPoint(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                value=0.7)))

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            remove_control_point=commands_pb2.RemoveControlPoint(
                point_id=track.points[0].id)))
        self.assertEqual(len(track.points), 0)

    async def test_move_control_point(self):
        track = await self._add_track()
        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            add_control_point=commands_pb2.AddControlPoint(
                time=audioproc.MusicalTime(1, 4).to_proto(),
                value=0.7)))

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            move_control_point=commands_pb2.MoveControlPoint(
                point_id=track.points[0].id,
                time=audioproc.MusicalTime(3, 4).to_proto(),
                value=0.6)))
        self.assertEqual(track.points[0].time, audioproc.MusicalTime(3, 4))
        self.assertAlmostEqual(track.points[0].value, 0.6)

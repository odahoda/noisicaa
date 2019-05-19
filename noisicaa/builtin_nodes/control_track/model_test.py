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

from typing import List

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisicaa import audioproc
from noisicaa.music import base_track_test
from noisicaa.music import project
from noisicaa.builtin_nodes import processor_message_registry_pb2
from . import model


class ControlTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()

        self.project = demo_project.empty(self.pool, project.BaseProject, node_db=self.node_db)
        self.track = self.pool.create(model.ControlTrack, name='test')
        self.project.nodes.append(self.track)

        self.messages = []  # type: List[str]

    def WhichOneof(self, msg):
        if msg.HasExtension(processor_message_registry_pb2.cvgenerator_add_control_point):
            return 'cvgenerator_add_control_point'
        if msg.HasExtension(processor_message_registry_pb2.cvgenerator_remove_control_point):
            return 'cvgenerator_remove_control_point'
        raise ValueError(msg)

    def message_cb(self, msg):
        self.assertEqual(int(msg.node_id, 16), self.track.id)
        # TODO: track the messages themselves and inspect their contents as well.
        self.messages.append(self.WhichOneof(msg))

    def test_messages_on_mutations(self):
        connector = self.track.create_node_connector(
            message_cb=self.message_cb, audioproc_client=None)
        try:
            self.assertEqual(connector.init(), [])

            self.messages.clear()
            self.track.points.insert(
                0,
                self.pool.create(
                    model.ControlPoint, time=audioproc.MusicalTime(1, 4), value=0.5))
            self.assertEqual(
                self.messages,
                ['cvgenerator_add_control_point'])

            self.messages.clear()
            self.track.points.insert(
                1,
                self.pool.create(
                    model.ControlPoint, time=audioproc.MusicalTime(2, 4), value=0.8))
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
            connector.cleanup()

    def test_messages_on_init(self):
        self.track.points.insert(
            0,
            self.pool.create(
                model.ControlPoint, time=audioproc.MusicalTime(1, 4), value=0.5))
        self.track.points.insert(
            1,
            self.pool.create(
                model.ControlPoint, time=audioproc.MusicalTime(2, 4), value=0.8))

        connector = self.track.create_node_connector(
            message_cb=self.message_cb, audioproc_client=None)
        try:
            messages = connector.init()

            self.assertEqual(
                [self.WhichOneof(msg) for msg in messages],
                ['cvgenerator_add_control_point',
                 'cvgenerator_add_control_point'])

        finally:
            connector.cleanup()


class ControlTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://control-track'
    track_cls = model.ControlTrack

    async def test_add_control_point(self):
        track = await self._add_track()

        with self.project.apply_mutations('test'):
            point = track.create_control_point(audioproc.MusicalTime(1, 4), 0.7)
        self.assertEqual(len(track.points), 1)
        self.assertIs(track.points[0], point)
        self.assertEqual(point.time, audioproc.MusicalTime(1, 4))
        self.assertAlmostEqual(point.value, 0.7)

    async def test_delete_control_point(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            point = track.create_control_point(audioproc.MusicalTime(1, 4), 0.7)

        with self.project.apply_mutations('test'):
            track.delete_control_point(point)
        self.assertEqual(len(track.points), 0)

    async def test_control_point_set_time(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            point = track.create_control_point(audioproc.MusicalTime(1, 4), 0.7)

        with self.project.apply_mutations('test'):
            point.time = audioproc.MusicalTime(3, 4)

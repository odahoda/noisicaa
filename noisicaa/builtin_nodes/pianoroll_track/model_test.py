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

from noisidev import unittest
from noisicaa import audioproc
from noisicaa.music import base_track_test
from . import model


# class ScoreTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
#     async def setup_testcase(self):
#         self.pool = project.Pool()

#     def test_foo(self):
#         pr = demo_project.basic(self.pool, project.BaseProject, node_db=self.node_db)
#         tr = pr.nodes[-1]

#         messages = []  # type: List[str]

#         connector = tr.create_node_connector(
#             message_cb=messages.append, audioproc_client=None)
#         try:
#             messages.extend(connector.init())

#             tr.insert_measure(1)
#             m = tr.measure_list[1].measure
#             m.notes.append(self.pool.create(model.Note, pitches=[value_types.Pitch('D#4')]))

#             self.assertTrue(len(messages) > 0)

#         finally:
#             connector.cleanup()


class PianoRollTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://pianoroll-track'
    track_cls = model.PianoRollTrack

    async def test_create_segment(self):
        track = await self._add_track()
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(
                audioproc.MusicalTime(3, 4),
                audioproc.MusicalDuration(4, 4))
        self.assertEqual(segment_ref.time, audioproc.MusicalTime(3, 4))
        self.assertEqual(segment_ref.segment.duration, audioproc.MusicalDuration(4, 4))
        self.assertEqual(len(track.segments), 1)
        self.assertIs(track.segments[0], segment_ref)
        self.assertEqual(len(track.segment_heap), 1)
        self.assertIs(track.segment_heap[0], segment_ref.segment)

    async def test_remove_segment(self):
        track = await self._add_track()
        with self.project.apply_mutations('test'):
            segment_ref = track.create_segment(
                audioproc.MusicalTime(3, 4),
                audioproc.MusicalDuration(4, 4))

        with self.project.apply_mutations('test'):
            track.remove_segment(segment_ref)
        self.assertEqual(len(track.segments), 0)
        self.assertEqual(len(track.segment_heap), 0)

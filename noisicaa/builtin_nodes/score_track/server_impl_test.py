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

# from typing import List

# from noisidev import unittest
# from noisidev import unittest_mixins
# from noisidev import demo_project
# from noisicaa import audioproc
# from noisicaa import model
# from noisicaa.music import pmodel_test
# from noisicaa.music import project
# from . import server_impl


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
#             m.notes.append(self.pool.create(server_impl.Note, pitches=[model.Pitch('D#4')]))

#             self.assertTrue(len(messages) > 0)

#         finally:
#             connector.close()


# class ScoreTrackTest(pmodel_test.MeasuredTrackMixin, pmodel_test.ModelTest):
#     cls = server_impl.ScoreTrack
#     create_args = {'name': 'test'}
#     measure_cls = server_impl.ScoreMeasure

#     def test_transpose_octaves(self):
#         track = self.pool.create(self.cls, **self.create_args)

#         self.assertEqual(track.transpose_octaves, 0)
#         track.transpose_octaves = -2
#         self.assertEqual(track.transpose_octaves, -2)


# class ScoreMeasureTest(pmodel_test.ModelTest):
#     def test_clef(self):
#         measure = self.pool.create(server_impl.ScoreMeasure)

#         self.assertEqual(measure.clef, model.Clef.Treble)
#         measure.clef = model.Clef.Tenor
#         self.assertEqual(measure.clef, model.Clef.Tenor)

#     def test_key_signature(self):
#         measure = self.pool.create(server_impl.ScoreMeasure)

#         self.assertEqual(measure.key_signature, model.KeySignature('C major'))
#         measure.key_signature = model.KeySignature('F minor')
#         self.assertEqual(measure.key_signature, model.KeySignature('F minor'))

#     def test_time_signature(self):
#         measure = self.pool.create(server_impl.ScoreMeasure)

#         self.assertEqual(measure.time_signature, model.TimeSignature(4, 4))
#         measure.time_signature = model.TimeSignature(3, 4)
#         self.assertEqual(measure.time_signature, model.TimeSignature(3, 4))

#     def test_notes(self):
#         measure = self.pool.create(server_impl.ScoreMeasure)

#         note = self.pool.create(server_impl.Note)
#         measure.notes.append(note)
#         self.assertIs(measure.notes[0], note)


# class NoteTest(pmodel_test.ModelTest):
#     def test_pitches(self):
#         note = self.pool.create(server_impl.Note)
#         self.assertEqual(len(note.pitches), 0)

#         note.pitches.append(model.Pitch('C4'))
#         note.pitches.append(model.Pitch('D4'))
#         note.pitches.append(model.Pitch('E4'))
#         note.pitches.append(model.Pitch('F4'))
#         del note.pitches[2]
#         note.pitches.insert(1, model.Pitch('G4'))
#         self.assertEqual(
#             note.pitches,
#             [model.Pitch('C4'), model.Pitch('G4'), model.Pitch('D4'), model.Pitch('F4')])

#     def test_base_duration(self):
#         note = self.pool.create(server_impl.Note)

#         note.base_duration = audioproc.MusicalDuration(1, 2)
#         self.assertEqual(note.base_duration, audioproc.MusicalDuration(1, 2))

#     def test_dots(self):
#         note = self.pool.create(server_impl.Note)

#         self.assertEqual(note.dots, 0)
#         note.dots = 2
#         self.assertEqual(note.dots, 2)

#     def test_tuplet(self):
#         note = self.pool.create(server_impl.Note)

#         self.assertEqual(note.tuplet, 0)
#         note.tuplet = 3
#         self.assertEqual(note.tuplet, 3)

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

from typing import List  # pylint: disable=unused-import

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import demo_project
from noisicaa import model
from noisicaa import audioproc
from . import project
from . import project_client
from . import score_track
from . import commands_pb2
from . import base_track_test


class ScoreTrackConnectorTest(unittest_mixins.NodeDBMixin, unittest.AsyncTestCase):
    async def setup_testcase(self):
        self.pool = project.Pool()

    def test_foo(self):
        pr = demo_project.basic(self.pool, project.BaseProject, node_db=self.node_db)
        tr = pr.pipeline_graph_nodes[-1]

        messages = []  # type: List[str]

        connector = tr.create_track_connector(message_cb=messages.append)
        try:
            messages.extend(connector.init())

            tr.insert_measure(1)
            m = tr.measure_list[1].measure
            m.notes.append(self.pool.create(score_track.Note, pitches=[model.Pitch('D#4')]))

            self.assertTrue(len(messages) > 0)

        finally:
            connector.close()


class ScoreTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://score_track'
    track_cls = project_client.ScoreTrack

    async def _fill_measure(self, measure):
        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            insert_note=commands_pb2.InsertNote(
                idx=0,
                pitch='F2',
                duration=audioproc.MusicalDuration(1, 4).to_proto())))
        self.assertEqual(len(measure.notes), 1)

    async def test_insert_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            insert_measure=commands_pb2.InsertMeasure(
                pos=0,
                tracks=[track.id])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_append_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            insert_measure=commands_pb2.InsertMeasure(
                tracks=[])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_remove_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            remove_measure=commands_pb2.RemoveMeasure(
                pos=0,
                tracks=[])))
        self.assertEqual(len(track.measure_list), 0)

    async def test_clear_measures(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)
        old_measure = track.measure_list[0].measure

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            clear_measures=commands_pb2.ClearMeasures(
                measure_ids=[track.measure_list[0].id])))
        self.assertIsNot(old_measure, track.measure_list[0].measure)

    async def test_set_clef(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            set_clef=commands_pb2.SetClef(
                measure_ids=[measure.id],
                clef=model.Clef.Tenor.to_proto())))
        self.assertEqual(measure.clef, model.Clef.Tenor)

    async def test_set_key_signature(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            set_key_signature=commands_pb2.SetKeySignature(
                measure_ids=[measure.id],
                key_signature=model.KeySignature('D minor').to_proto())))
        self.assertEqual(measure.key_signature, model.KeySignature('D minor'))

    async def test_transpose_octaves(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            update_track_properties=commands_pb2.UpdateTrackProperties(
                transpose_octaves=1)))
        self.assertEqual(track.transpose_octaves, 1)

    async def test_insert_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        self.assertEqual(len(measure.notes), 0)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            insert_note=commands_pb2.InsertNote(
                idx=0,
                pitch='F2',
                duration=audioproc.MusicalDuration(1, 4).to_proto())))
        self.assertEqual(len(measure.notes), 1)
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('F2'))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 4))

    async def test_delete_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            delete_note=commands_pb2.DeleteNote(
                idx=0)))
        self.assertEqual(len(measure.notes), 0)

    async def test_change_note_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            change_note=commands_pb2.ChangeNote(
                idx=0,
                pitch='C2')))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('C2'))

    async def test_change_note_duration(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            change_note=commands_pb2.ChangeNote(
                idx=0,
                duration=audioproc.MusicalDuration(1, 2).to_proto())))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 2))

    async def test_change_note_dots(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            change_note=commands_pb2.ChangeNote(
                idx=0,
                dots=1)))
        self.assertEqual(measure.notes[0].dots, 1)

    async def test_change_note_tuplet(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            change_note=commands_pb2.ChangeNote(
                idx=0,
                tuplet=3)))
        self.assertEqual(measure.notes[0].tuplet, 3)

    async def test_set_accidental(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            set_accidental=commands_pb2.SetAccidental(
                idx=0,
                pitch_idx=0,
                accidental='#')))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('F#2'))

    async def test_add_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            add_pitch=commands_pb2.AddPitch(
                idx=0,
                pitch='C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)
        self.assertEqual(measure.notes[0].pitches[1], model.Pitch('C2'))

    async def test_remove_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)
        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            add_pitch=commands_pb2.AddPitch(
                idx=0,
                pitch='C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            remove_pitch=commands_pb2.RemovePitch(
                idx=0,
                pitch_idx=0)))
        self.assertEqual(len(measure.notes[0].pitches), 1)
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('C2'))

    async def test_transpose_notes(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            transpose_notes=commands_pb2.TransposeNotes(
                note_ids=[measure.notes[0].id],
                half_notes=2)))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('G2'))

    async def test_paste_overwrite(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        clipboard = measure.serialize()

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            paste_measures=commands_pb2.PasteMeasures(
                mode='overwrite',
                src_objs=[clipboard],
                target_ids=[track.measure_list[0].id])))
        new_measure = track.measure_list[0].measure
        self.assertNotEqual(new_measure.id, measure.id)
        self.assertEqual(new_measure.notes[0].pitches[0], model.Pitch('F2'))

    # async def test_paste_link(self):
    #     track = await self._add_track(num_measures=3)

    #     measure = track.measure_list[0].measure
    #     await self._fill_measure(measure)

    #     clipboard = measure.serialize()

    #     await self.client.send_command(commands_pb2.Command(
    #         target=self.project.id,
    #         paste_measures=commands_pb2.PasteMeasures(
    #             mode='link',
    #             src_objs=[clipboard],
    #             target_ids=[track.measure_list[1].id, track.measure_list[2].id])))
    #     self.assertIs(track.measure_list[1].measure, measure)
    #     self.assertIs(track.measure_list[2].measure, measure)

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
from noisicaa import model
from noisicaa.music import base_track_test
from noisicaa.music import commands_pb2
from . import client_impl
from . import commands


class ScoreTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://score-track'
    track_cls = client_impl.ScoreTrack

    async def _fill_measure(self, measure):
        await self.client.send_command(commands.insert_note(
            measure.id,
            idx=0,
            pitch=model.Pitch('F2'),
            duration=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(len(measure.notes), 1)

    async def test_insert_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            command='insert_measure',
            insert_measure=commands_pb2.InsertMeasure(
                pos=0,
                tracks=[track.id])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_append_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            command='insert_measure',
            insert_measure=commands_pb2.InsertMeasure(
                tracks=[])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_remove_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            command='remove_measure',
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
            command='clear_measures',
            clear_measures=commands_pb2.ClearMeasures(
                measure_ids=[track.measure_list[0].id])))
        self.assertIsNot(old_measure, track.measure_list[0].measure)

    async def test_set_clef(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands.set_clef(
            track.id,
            measure_ids=[measure.id],
            clef=model.Clef.Tenor))
        self.assertEqual(measure.clef, model.Clef.Tenor)

    async def test_set_key_signature(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands.set_key_signature(
            track.id,
            measure_ids=[measure.id],
            key_signature=model.KeySignature('D minor')))
        self.assertEqual(measure.key_signature, model.KeySignature('D minor'))

    async def test_transpose_octaves(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            command='update_track_properties',
            update_track_properties=commands_pb2.UpdateTrackProperties(
                transpose_octaves=1)))
        self.assertEqual(track.transpose_octaves, 1)

    async def test_insert_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        self.assertEqual(len(measure.notes), 0)

        await self.client.send_command(commands.insert_note(
            measure.id,
            idx=0,
            pitch=model.Pitch('F2'),
            duration=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(len(measure.notes), 1)
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('F2'))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 4))

    async def test_delete_note(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.delete_note(
            measure.id,
            idx=0))
        self.assertEqual(len(measure.notes), 0)

    async def test_change_note_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.change_note(
            measure.id,
            idx=0,
            pitch=model.Pitch('C2')))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('C2'))

    async def test_change_note_duration(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.change_note(
            measure.id,
            idx=0,
            duration=audioproc.MusicalDuration(1, 2)))
        self.assertEqual(measure.notes[0].base_duration, audioproc.MusicalDuration(1, 2))

    async def test_change_note_dots(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.change_note(
            measure.id,
            idx=0,
            dots=1))
        self.assertEqual(measure.notes[0].dots, 1)

    async def test_change_note_tuplet(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.change_note(
            measure.id,
            idx=0,
            tuplet=3))
        self.assertEqual(measure.notes[0].tuplet, 3)

    async def test_set_accidental(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.set_accidental(
            measure.id,
            idx=0,
            pitch_idx=0,
            accidental='#'))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('F#2'))

    async def test_add_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.add_pitch(
            measure.id,
            idx=0,
            pitch=model.Pitch('C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)
        self.assertEqual(measure.notes[0].pitches[1], model.Pitch('C2'))

    async def test_remove_pitch(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)
        await self.client.send_command(commands.add_pitch(
            measure.id,
            idx=0,
            pitch=model.Pitch('C2')))
        self.assertEqual(len(measure.notes[0].pitches), 2)

        await self.client.send_command(commands.remove_pitch(
            measure.id,
            idx=0,
            pitch_idx=0))
        self.assertEqual(len(measure.notes[0].pitches), 1)
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('C2'))

    async def test_transpose_notes(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        await self.client.send_command(commands.transpose_notes(
            track.id,
            note_ids=[measure.notes[0].id],
            half_notes=2))
        self.assertEqual(measure.notes[0].pitches[0], model.Pitch('G2'))

    async def test_paste_overwrite(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self._fill_measure(measure)

        clipboard = measure.serialize()

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            command='paste_measures',
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

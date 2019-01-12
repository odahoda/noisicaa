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


class BeatTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://beat-track'
    track_cls = client_impl.BeatTrack

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

    async def test_set_beat_track_pitch(self):
        track = await self._add_track()

        await self.client.send_command(commands.set_beat_track_pitch(
            track.id,
            pitch=model.Pitch('C2')))
        self.assertEqual(track.pitch, model.Pitch('C2'))

    async def test_add_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands.add_beat(
            measure.id,
            time=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(measure.beats[0].time, audioproc.MusicalDuration(1, 4))
        self.assertEqual(measure.beats[0].velocity, 100)

    async def test_remove_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands.add_beat(
            measure.id,
            time=audioproc.MusicalDuration(1, 4)))

        await self.client.send_command(commands.remove_beat(
            measure.id,
            beat_id=measure.beats[0].id))
        self.assertEqual(len(measure.beats), 0)

    async def test_set_beat_velocity(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands.add_beat(
            measure.id,
            time=audioproc.MusicalDuration(1, 4)))
        beat = measure.beats[0]

        await self.client.send_command(commands.set_beat_velocity(
            beat.id,
            velocity=57))
        self.assertEqual(beat.velocity, 57)

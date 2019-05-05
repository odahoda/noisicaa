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
from noisicaa import value_types
from noisicaa.music import base_track_test
from . import model
from . import commands


class BeatTrackTest(base_track_test.TrackTestMixin, unittest.AsyncTestCase):
    node_uri = 'builtin://beat-track'
    track_cls = model.BeatTrack

    async def test_create_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        with self.project.apply_mutations():
            track.insert_measure(0)
        self.assertEqual(len(track.measure_list), 2)

    async def test_delete_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        with self.project.apply_mutations():
            track.remove_measure(0)
        self.assertEqual(len(track.measure_list), 0)

    async def test_clear_measures(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)
        old_measure = track.measure_list[0].measure

        with self.project.apply_mutations():
            track.measure_list[0].clear_measure()
        self.assertIsNot(old_measure, track.measure_list[0].measure)

    async def test_set_pitch(self):
        track = await self._add_track()

        await self.client.send_command(commands.update(
            track,
            set_pitch=value_types.Pitch('C2')))
        self.assertEqual(track.pitch, value_types.Pitch('C2'))

    async def test_add_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands.create_beat(
            measure,
            time=audioproc.MusicalDuration(1, 4)))
        self.assertEqual(measure.beats[0].time, audioproc.MusicalDuration(1, 4))
        self.assertEqual(measure.beats[0].velocity, 100)

        await self.client.send_command(commands.create_beat(
            measure,
            time=audioproc.MusicalDuration(2, 4),
            velocity=120))
        self.assertEqual(measure.beats[1].time, audioproc.MusicalDuration(2, 4))
        self.assertEqual(measure.beats[1].velocity, 120)

    async def test_delete_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands.create_beat(
            measure,
            time=audioproc.MusicalDuration(1, 4)))

        await self.client.send_command(commands.delete_beat(
            measure.beats[0]))
        self.assertEqual(len(measure.beats), 0)

    async def test_beat_set_velocity(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands.create_beat(
            measure,
            time=audioproc.MusicalDuration(1, 4)))
        beat = measure.beats[0]

        await self.client.send_command(commands.update_beat(
            beat,
            set_velocity=57))
        self.assertEqual(beat.velocity, 57)

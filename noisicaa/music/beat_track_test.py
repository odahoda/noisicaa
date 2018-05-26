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

from noisicaa import audioproc
from noisicaa import model
from . import project_client
from . import commands_pb2
from . import commands_test

logger = logging.getLogger(__name__)


class BeatTrackTest(commands_test.CommandsTestBase):
    async def test_add_remove(self):
        insert_index = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='beat',
                parent_group_id=self.project.master_group.id)))
        self.assertEqual(insert_index, 0)

        track = self.project.master_group.tracks[insert_index]
        self.assertIsInstance(track, project_client.BeatTrack)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            remove_track=commands_pb2.RemoveTrack(
                track_id=track.id)))
        self.assertEqual(len(self.project.master_group.tracks), 0)

    async def _add_track(self):
        insert_index = await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            add_track=commands_pb2.AddTrack(
                track_type='beat',
                parent_group_id=self.project.master_group.id)))
        return self.project.master_group.tracks[insert_index]

    async def test_set_num_measures(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            set_num_measures=commands_pb2.SetNumMeasures(
                num_measures=10)))
        self.assertEqual(len(track.measure_list), 10)
        self.assertEqual(self.project.duration, audioproc.MusicalDuration(10 * 4, 4))

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            set_num_measures=commands_pb2.SetNumMeasures(
                num_measures=5)))
        self.assertEqual(len(track.measure_list), 5)

    async def test_insert_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            insert_measure=commands_pb2.InsertMeasure(
                pos=0,
                tracks=[track.id])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_append_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
            insert_measure=commands_pb2.InsertMeasure(
                tracks=[])))
        self.assertEqual(len(track.measure_list), 2)

    async def test_remove_measure(self):
        track = await self._add_track()
        self.assertEqual(len(track.measure_list), 1)

        await self.client.send_command(commands_pb2.Command(
            target=self.project.id,
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

    async def test_set_beat_track_instrument(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            set_beat_track_instrument=commands_pb2.SetBeatTrackInstrument(
                instrument='sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=2')))
        self.assertEqual(
            track.instrument, 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=2')

    async def test_set_beat_track_pitch(self):
        track = await self._add_track()

        await self.client.send_command(commands_pb2.Command(
            target=track.id,
            set_beat_track_pitch=commands_pb2.SetBeatTrackPitch(
                pitch=model.Pitch('C2').to_proto())))
        self.assertEqual(track.pitch, model.Pitch('C2'))

    async def test_add_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            add_beat=commands_pb2.AddBeat(
                time=audioproc.MusicalDuration(1, 4).to_proto())))
        self.assertEqual(measure.beats[0].time, audioproc.MusicalDuration(1, 4))
        self.assertEqual(measure.beats[0].velocity, 100)

    async def test_remove_beat(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            add_beat=commands_pb2.AddBeat(
                time=audioproc.MusicalDuration(1, 4).to_proto())))

        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            remove_beat=commands_pb2.RemoveBeat(
                beat_id=measure.beats[0].id)))
        self.assertEqual(len(measure.beats), 0)

    async def test_set_beat_velocity(self):
        track = await self._add_track()
        measure = track.measure_list[0].measure
        await self.client.send_command(commands_pb2.Command(
            target=measure.id,
            add_beat=commands_pb2.AddBeat(
                time=audioproc.MusicalDuration(1, 4).to_proto())))
        beat = measure.beats[0]

        await self.client.send_command(commands_pb2.Command(
            target=beat.id,
            set_beat_velocity=commands_pb2.SetBeatVelocity(
                velocity=57)))
        self.assertEqual(beat.velocity, 57)

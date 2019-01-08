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

from noisicaa import audioproc
from noisicaa import model
from noisicaa.music import pmodel_test
from . import server_impl

T0 = audioproc.MusicalDuration(0, 4)


class BeatTrackTest(pmodel_test.MeasuredTrackMixin, pmodel_test.ModelTest):
    cls = server_impl.BeatTrack
    create_args = {'name': 'test'}
    measure_cls = server_impl.BeatMeasure

    def test_pitch(self):
        track = self.pool.create(self.cls, **self.create_args)

        track.pitch = model.Pitch('F4')
        self.assertEqual(track.pitch, model.Pitch('F4'))


class BeatMeasureTest(pmodel_test.ModelTest):
    def test_beats(self):
        measure = self.pool.create(server_impl.BeatMeasure)

        beat = self.pool.create(server_impl.Beat, time=T0, velocity=100)
        measure.beats.append(beat)
        self.assertIs(measure.beats[0], beat)


class BeatTest(pmodel_test.ModelTest):
    def test_time(self):
        beat = self.pool.create(server_impl.Beat, time=T0, velocity=100)

        beat.time = audioproc.MusicalDuration(1, 4)
        self.assertEqual(beat.time, audioproc.MusicalDuration(1, 4))

    def test_velocity(self):
        beat = self.pool.create(server_impl.Beat, time=T0, velocity=100)

        beat.velocity = 120
        self.assertEqual(beat.velocity, 120)

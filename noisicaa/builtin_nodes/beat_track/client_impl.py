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

from typing import Sequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa.music import project_client_model
from . import model as beat_track_model


class Beat(
        project_client_model.ProjectChild,
        beat_track_model.Beat,
        project_client_model.ObjectBase):
    @property
    def time(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration.from_proto(self.get_property_value('time'))

    @property
    def velocity(self) -> int:
        return self.get_property_value('velocity')

    @property
    def measure(self) -> 'BeatMeasure':
        return down_cast(BeatMeasure, super().measure)


class BeatMeasure(
        project_client_model.Measure,
        beat_track_model.BeatMeasure,
        project_client_model.ObjectBase):
    @property
    def beats(self) -> Sequence[Beat]:
        return self.get_property_value('beats')


class BeatTrack(
        project_client_model.MeasuredTrack,
        beat_track_model.BeatTrack,
        project_client_model.ObjectBase):
    @property
    def pitch(self) -> model.Pitch:
        return self.get_property_value('pitch')

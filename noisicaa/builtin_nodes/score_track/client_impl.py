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

from typing import Sequence

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa.music import project_client_model
from . import model as score_track_model


class Note(
        project_client_model.ProjectChild,
        score_track_model.Note,
        project_client_model.ObjectBase):
    @property
    def pitches(self) -> Sequence[model.Pitch]:
        return self.get_property_value('pitches')

    @property
    def base_duration(self) -> audioproc.MusicalDuration:
        return self.get_property_value('base_duration')

    @property
    def dots(self) -> int:
        return self.get_property_value('dots')

    @property
    def tuplet(self) -> int:
        return self.get_property_value('tuplet')

    @property
    def measure(self) -> 'ScoreMeasure':
        return down_cast(ScoreMeasure, super().measure)


class ScoreMeasure(
        project_client_model.Measure,
        score_track_model.ScoreMeasure,
        project_client_model.ObjectBase):
    @property
    def clef(self) -> model.Clef:
        return self.get_property_value('clef')

    @property
    def key_signature(self) -> model.KeySignature:
        return self.get_property_value('key_signature')

    @property
    def notes(self) -> Sequence[Note]:
        return self.get_property_value('notes')

    @property
    def track(self) -> 'ScoreTrack':
        return down_cast(ScoreTrack, super().track)


class ScoreTrack(
        project_client_model.MeasuredTrack,
        score_track_model.ScoreTrack,
        project_client_model.ObjectBase):
    @property
    def transpose_octaves(self) -> int:
        return self.get_property_value('transpose_octaves')

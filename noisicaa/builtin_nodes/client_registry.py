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

from noisicaa import model
from .score_track.client_impl import Note, ScoreMeasure, ScoreTrack
from .beat_track.client_impl import Beat, BeatMeasure, BeatTrack
from .control_track.client_impl import ControlPoint, ControlTrack
from .sample_track.client_impl import SampleRef, SampleTrack
from .instrument.client_impl import Instrument
from .custom_csound.client_impl import CustomCSound, CustomCSoundPort
from .midi_source.client_impl import MidiSource


def register_classes(pool: model.AbstractPool) -> None:
    pool.register_class(Note)
    pool.register_class(ScoreMeasure)
    pool.register_class(ScoreTrack)
    pool.register_class(Beat)
    pool.register_class(BeatMeasure)
    pool.register_class(BeatTrack)
    pool.register_class(ControlPoint)
    pool.register_class(ControlTrack)
    pool.register_class(SampleRef)
    pool.register_class(SampleTrack)
    pool.register_class(Instrument)
    pool.register_class(CustomCSoundPort)
    pool.register_class(CustomCSound)
    pool.register_class(MidiSource)

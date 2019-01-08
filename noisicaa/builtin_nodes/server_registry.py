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

from typing import Dict, Type

from noisicaa import model
from noisicaa.music import pipeline_graph
from .score_track.server_impl import Note, ScoreMeasure, ScoreTrack
from .beat_track.server_impl import Beat, BeatMeasure, BeatTrack
from .control_track.server_impl import ControlPoint, ControlTrack
from .sample_track.server_impl import SampleRef, SampleTrack
from .instrument.server_impl import Instrument
from .custom_csound.server_impl import CustomCSound


node_cls_map = {
    'builtin://score-track': ScoreTrack,
    'builtin://beat-track': BeatTrack,
    'builtin://control-track': ControlTrack,
    'builtin://sample-track': SampleTrack,
    'builtin://instrument': Instrument,
    'builtin://custom-csound': CustomCSound,
}  # type: Dict[str, Type[pipeline_graph.BasePipelineGraphNode]]


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
    pool.register_class(CustomCSound)

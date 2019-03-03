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

from typing import Dict, Type

from noisicaa import model
from noisicaa.core import ipc
from noisicaa.music import commands
from noisicaa.music import graph
from noisicaa.music import project_process_context
from .score_track import server_impl as score_track
from .beat_track import server_impl as beat_track
from .control_track import server_impl as control_track
from .sample_track import server_impl as sample_track
from .instrument import server_impl as instrument
from .custom_csound import server_impl as custom_csound
from .midi_source import server_impl as midi_source


node_cls_map = {
    'builtin://score-track': score_track.ScoreTrack,
    'builtin://beat-track': beat_track.BeatTrack,
    'builtin://control-track': control_track.ControlTrack,
    'builtin://sample-track': sample_track.SampleTrack,
    'builtin://instrument': instrument.Instrument,
    'builtin://custom-csound': custom_csound.CustomCSound,
    'builtin://midi-source': midi_source.MidiSource,
}  # type: Dict[str, Type[graph.BaseNode]]


def register_classes(pool: model.AbstractPool) -> None:
    pool.register_class(score_track.Note)
    pool.register_class(score_track.ScoreMeasure)
    pool.register_class(score_track.ScoreTrack)
    pool.register_class(beat_track.Beat)
    pool.register_class(beat_track.BeatMeasure)
    pool.register_class(beat_track.BeatTrack)
    pool.register_class(control_track.ControlPoint)
    pool.register_class(control_track.ControlTrack)
    pool.register_class(sample_track.SampleRef)
    pool.register_class(sample_track.SampleTrack)
    pool.register_class(instrument.Instrument)
    pool.register_class(custom_csound.CustomCSound)
    pool.register_class(midi_source.MidiSource)


def register_commands(registry: commands.CommandRegistry) -> None:
    registry.register(score_track.UpdateScoreTrack)
    registry.register(score_track.UpdateScoreMeasure)
    registry.register(score_track.CreateNote)
    registry.register(score_track.UpdateNote)
    registry.register(score_track.DeleteNote)
    registry.register(beat_track.UpdateBeatTrack)
    registry.register(beat_track.CreateBeat)
    registry.register(beat_track.UpdateBeat)
    registry.register(beat_track.DeleteBeat)
    registry.register(control_track.CreateControlPoint)
    registry.register(control_track.UpdateControlPoint)
    registry.register(control_track.DeleteControlPoint)
    registry.register(sample_track.CreateSample)
    registry.register(sample_track.DeleteSample)
    registry.register(sample_track.UpdateSample)
    registry.register(instrument.UpdateInstrument)
    registry.register(custom_csound.UpdateCustomCSound)
    registry.register(midi_source.UpdateMidiSource)


def register_ipc_handlers(
        ctxt: project_process_context.ProjectProcessContext,
        endpoint: ipc.ServerEndpointWithSessions
) -> None:
    sample_track.register_ipc_handlers(ctxt, endpoint)

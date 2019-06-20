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

from noisicaa import music
from noisicaa.music import graph
from .score_track import model as score_track
from .beat_track import model as beat_track
from .control_track import model as control_track
from .sample_track import model as sample_track
from .instrument import model as instrument
from .custom_csound import model as custom_csound
from .midi_source import model as midi_source
from .step_sequencer import model as step_sequencer
from .midi_cc_to_cv import model as midi_cc_to_cv
from .midi_looper import model as midi_looper


node_cls_map = {
    'builtin://score-track': score_track.ScoreTrack,
    'builtin://beat-track': beat_track.BeatTrack,
    'builtin://control-track': control_track.ControlTrack,
    'builtin://sample-track': sample_track.SampleTrack,
    'builtin://instrument': instrument.Instrument,
    'builtin://custom-csound': custom_csound.CustomCSound,
    'builtin://midi-source': midi_source.MidiSource,
    'builtin://step-sequencer': step_sequencer.StepSequencer,
    'builtin://midi-cc-to-cv': midi_cc_to_cv.MidiCCtoCV,
    'builtin://midi-looper': midi_looper.MidiLooper,
}  # type: Dict[str, Type[graph.BaseNode]]


def register_classes(pool: music.Pool) -> None:
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
    pool.register_class(custom_csound.CustomCSoundPort)
    pool.register_class(custom_csound.CustomCSound)
    pool.register_class(midi_source.MidiSource)
    pool.register_class(step_sequencer.StepSequencer)
    pool.register_class(step_sequencer.StepSequencerChannel)
    pool.register_class(step_sequencer.StepSequencerStep)
    pool.register_class(midi_cc_to_cv.MidiCCtoCV)
    pool.register_class(midi_cc_to_cv.MidiCCtoCVChannel)
    pool.register_class(midi_looper.MidiLooper)
    pool.register_class(midi_looper.MidiLooperPatch)

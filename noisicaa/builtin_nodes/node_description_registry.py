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

from typing import Iterator

from noisicaa import node_db
from .score_track.node_description import ScoreTrackDescription
from .beat_track.node_description import BeatTrackDescription
from .control_track.node_description import ControlTrackDescription
from .sample_track.node_description import SampleTrackDescription
from .instrument.node_description import InstrumentDescription
from .mixer.node_description import MixerDescription
from .custom_csound.node_description import CustomCSoundDescription
from .midi_source.node_description import MidiSourceDescription
from .oscillator.node_description import OscillatorDescription
from .vca.node_description import VCADescription
from .noise.node_description import NoiseDescription
from .step_sequencer.node_description import StepSequencerDescription
from .midi_cc_to_cv.node_description import MidiCCtoCVDescription
from .midi_looper.node_description import MidiLooperDescription
from .midi_monitor.node_description import MidiMonitorDescription
from .metronome.node_description import MetronomeDescription
from .midi_velocity_mapper.node_description import MidiVelocityMapperDescription
from .cv_mapper.node_description import CVMapperDescription


def node_descriptions() -> Iterator[node_db.NodeDescription]:
    yield ScoreTrackDescription
    yield BeatTrackDescription
    yield ControlTrackDescription
    yield SampleTrackDescription
    yield InstrumentDescription
    yield MixerDescription
    yield CustomCSoundDescription
    yield MidiSourceDescription
    yield OscillatorDescription
    yield VCADescription
    yield NoiseDescription
    yield StepSequencerDescription
    yield MidiCCtoCVDescription
    yield MidiLooperDescription
    yield MidiMonitorDescription
    yield MetronomeDescription
    yield MidiVelocityMapperDescription
    yield CVMapperDescription

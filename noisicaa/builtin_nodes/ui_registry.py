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

import typing
from typing import Dict, Type

from .score_track.node_ui import ScoreTrackNode
from .score_track.track_ui import ScoreTrackEditor
from .beat_track.node_ui import BeatTrackNode
from .beat_track.track_ui import BeatTrackEditor
from .control_track.node_ui import ControlTrackNode
from .control_track.track_ui import ControlTrackEditor
from .sample_track.node_ui import SampleTrackNode
from .sample_track.track_ui import SampleTrackEditor
from .instrument.node_ui import InstrumentNode
from .mixer.node_ui import MixerNode
from .custom_csound.node_ui import CustomCSoundNode
from .midi_source.node_ui import MidiSourceNode
from .step_sequencer.node_ui import StepSequencerNode
from .midi_cc_to_cv.node_ui import MidiCCtoCVNode
from .midi_looper.node_ui import MidiLooperNode
from .midi_monitor.node_ui import MidiMonitorNode
from .metronome.node_ui import MetronomeNode
from .midi_velocity_mapper.node_ui import MidiVelocityMapperNode

if typing.TYPE_CHECKING:
    from noisicaa.ui.graph import base_node
    from noisicaa.ui.track_list import base_track_editor


node_ui_cls_map = {
    'builtin://score-track': ScoreTrackNode,
    'builtin://beat-track': BeatTrackNode,
    'builtin://control-track': ControlTrackNode,
    'builtin://sample-track': SampleTrackNode,
    'builtin://instrument': InstrumentNode,
    'builtin://mixer': MixerNode,
    'builtin://custom-csound': CustomCSoundNode,
    'builtin://midi-source': MidiSourceNode,
    'builtin://step-sequencer': StepSequencerNode,
    'builtin://midi-cc-to-cv': MidiCCtoCVNode,
    'builtin://midi-looper': MidiLooperNode,
    'builtin://midi-monitor': MidiMonitorNode,
    'builtin://metronome': MetronomeNode,
    'builtin://midi-velocity-mapper': MidiVelocityMapperNode,
}  # type: Dict[str, Type[base_node.Node]]

track_editor_cls_map = {
    'ScoreTrack': ScoreTrackEditor,
    'BeatTrack': BeatTrackEditor,
    'ControlTrack': ControlTrackEditor,
    'SampleTrack': SampleTrackEditor,
}  # type: Dict[str, Type[base_track_editor.BaseTrackEditor]]

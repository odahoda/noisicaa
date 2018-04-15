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

# TODO: pylint-unclean
# mypy: loose

import functools
import logging
from typing import cast

from noisicaa import core
from noisicaa import audioproc

from .pitch import Pitch
from . import model
from . import state
from . import commands
from . import pipeline_graph
from . import misc
from . import base_track
from . import project

logger = logging.getLogger(__name__)


class SetBeatTrackInstrument(commands.Command):
    instrument = core.Property(str)

    def __init__(self, instrument=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument = instrument

    def run(self, track):
        assert isinstance(track, BeatTrack)

        track.instrument = self.instrument

        for mutation in track.instrument_node.get_update_mutations():
            cast(project.BaseProject, project).handle_pipeline_mutation(mutation)

commands.Command.register_command(SetBeatTrackInstrument)


class SetBeatTrackPitch(commands.Command):
    pitch = core.Property(Pitch)

    def __init__(self, pitch=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.pitch = pitch

    def run(self, track):
        assert isinstance(track, BeatTrack)

        track.pitch = self.pitch

commands.Command.register_command(SetBeatTrackPitch)


class SetBeatVelocity(commands.Command):
    velocity = core.Property(int)

    def __init__(self, velocity=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.velocity = velocity

    def run(self, beat):
        assert isinstance(beat, Beat)

        beat.velocity = self.velocity

commands.Command.register_command(SetBeatVelocity)


class AddBeat(commands.Command):
    time = core.Property(audioproc.MusicalDuration)

    def __init__(self, time=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.time = time

    def run(self, measure):
        assert isinstance(measure, BeatMeasure)

        beat = Beat(time=self.time, velocity=100)
        assert audioproc.MusicalDuration(0, 1) <= beat.time < measure.duration
        measure.beats.append(beat)

commands.Command.register_command(AddBeat)


class RemoveBeat(commands.Command):
    beat_id = core.Property(str)

    def __init__(self, beat_id=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.beat_id = beat_id

    def run(self, measure):
        assert isinstance(measure, BeatMeasure)

        root = measure.root
        beat = root.get_object(self.beat_id)
        assert beat.is_child_of(measure)
        del measure.beats[beat.index]

commands.Command.register_command(RemoveBeat)


class Beat(model.Beat, state.StateBase):
    def __init__(self,
                 time=None, velocity=None,
                 state=None):
        super().__init__(state=state)
        if state is None:
            self.time = time
            self.velocity = velocity

    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('beats-changed')

state.StateBase.register_class(Beat)


class BeatMeasure(model.BeatMeasure, base_track.Measure):
    def __init__(self, state=None):
        super().__init__(state=state)
        self.listeners.add(
            'beats', lambda *args: self.listeners.call('beats-changed'))

    @property
    def empty(self):
        return len(self.beats) == 0

state.StateBase.register_class(BeatMeasure)


class BeatTrackConnector(base_track.MeasuredTrackConnector):
    def _add_track_listeners(self):
        self._listeners['pitch'] = self._track.listeners.add(
            'pitch', self.__pitch_changed)

    def _add_measure_listeners(self, mref):
        self._listeners['measure:%s:beats' % mref.id] = mref.measure.listeners.add(
            'beats-changed', functools.partial(
                self.__measure_beats_changed, mref))

    def _remove_measure_listeners(self, mref):
        self._listeners.pop('measure:%s:beats' % mref.id).remove()

    def _create_events(self, time, measure):
        for beat in measure.beats:
            beat_time = time + beat.time
            event = base_track.PianoRollInterval(
                beat_time, beat_time + audioproc.MusicalDuration(1, 4),
                self._track.pitch, 127)
            yield event

    def __pitch_changed(self, change):
        self._update_measure_range(0, len(self._track.measure_list))

    def __measure_beats_changed(self, mref):
        self._update_measure_range(mref.index, mref.index + 1)


class BeatTrack(model.BeatTrack, base_track.MeasuredTrack):
    measure_cls = BeatMeasure

    def __init__(
            self, instrument=None, pitch=None, num_measures=1,
            state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            if instrument is None:
                self.instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=128&preset=0'
            else:
                self.instrument = instrument

            if pitch is None:
                self.pitch = Pitch('B2')
            else:
                self.pitch = pitch

            for _ in range(num_measures):
                self.append_measure()

    def create_track_connector(self, **kwargs):
        return BeatTrackConnector(
            track=self,
            node_id=self.event_source_name,
            **kwargs)

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    @property
    def event_source_node(self):
        if self.event_source_id is None:
            raise ValueError("No event source node found.")
        return self.root.get_object(self.event_source_id)

    @property
    def instr_name(self):
        return '%s-instr' % self.id

    @property
    def instrument_node(self):
        if self.instrument_id is None:
            raise ValueError("No instrument node found.")

        return self.root.get_object(self.instrument_id)

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        instrument_node = pipeline_graph.InstrumentPipelineGraphNode(
            name="Track Instrument",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(instrument_node)
        self.instrument_id = instrument_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                instrument_node, 'out:left', self.mixer_node, 'in:left'))
        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                instrument_node, 'out:right', self.mixer_node, 'in:right'))

        event_source_node = pipeline_graph.PianoRollPipelineGraphNode(
            name="Track Events",
            graph_pos=instrument_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(event_source_node)
        self.event_source_id = event_source_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                event_source_node, 'out', instrument_node, 'in'))

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.event_source_node)
        self.event_source_id = None
        self.project.remove_pipeline_graph_node(self.instrument_node)
        self.instrument_id = None
        super().remove_pipeline_nodes()

state.StateBase.register_class(BeatTrack)

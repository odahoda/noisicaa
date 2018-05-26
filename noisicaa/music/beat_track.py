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

import functools
import logging
from typing import Any, Optional, Iterator

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model

from . import pmodel
from . import pipeline_graph
from . import base_track
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class SetBeatTrackInstrument(commands.Command):
    proto_type = 'set_beat_track_instrument'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetBeatTrackInstrument, pb)
        track = down_cast(pmodel.BeatTrack, pool[self.proto.command.target])

        track.instrument = pb.instrument

        for mutation in track.instrument_node.get_update_mutations():
            project.handle_pipeline_mutation(mutation)

commands.Command.register_command(SetBeatTrackInstrument)


class SetBeatTrackPitch(commands.Command):
    proto_type = 'set_beat_track_pitch'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetBeatTrackPitch, pb)
        track = down_cast(pmodel.BeatTrack, pool[self.proto.command.target])

        track.pitch = model.Pitch.from_proto(pb.pitch)

commands.Command.register_command(SetBeatTrackPitch)


class SetBeatVelocity(commands.Command):
    proto_type = 'set_beat_velocity'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetBeatVelocity, pb)
        beat = down_cast(pmodel.Beat, pool[self.proto.command.target])

        beat.velocity = pb.velocity

commands.Command.register_command(SetBeatVelocity)


class AddBeat(commands.Command):
    proto_type = 'add_beat'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddBeat, pb)
        measure = down_cast(pmodel.BeatMeasure, pool[self.proto.command.target])

        beat = pool.create(
            Beat,
            time=audioproc.MusicalDuration.from_proto(pb.time),
            velocity=100)
        assert audioproc.MusicalDuration(0, 1) <= beat.time < measure.duration
        measure.beats.append(beat)

commands.Command.register_command(AddBeat)


class RemoveBeat(commands.Command):
    proto_type = 'remove_beat'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveBeat, pb)
        measure = down_cast(pmodel.BeatMeasure, pool[self.proto.command.target])

        beat = down_cast(pmodel.Beat, pool[pb.beat_id])
        assert beat.is_child_of(measure)
        del measure.beats[beat.index]

commands.Command.register_command(RemoveBeat)


class Beat(pmodel.Beat):
    def create(
            self, *, time: Optional[audioproc.MusicalTime] = None, velocity: Optional[int] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.velocity = velocity

    def property_changed(self, change: model.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.listeners.call('beats-changed')


class BeatMeasure(pmodel.BeatMeasure, base_track.Measure):
    def setup(self) -> None:
        super().setup()
        self.listeners.add('beats', lambda *args: self.listeners.call('beats-changed'))

    @property
    def empty(self) -> bool:
        return len(self.beats) == 0


class BeatTrackConnector(base_track.MeasuredTrackConnector):
    _track = None  # type: BeatTrack

    def _add_track_listeners(self) -> None:
        self._listeners['pitch'] = self._track.listeners.add('pitch', self.__pitch_changed)

    def _add_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        self._listeners['measure:%s:beats' % mref.id] = mref.measure.listeners.add(
            'beats-changed', functools.partial(self.__measure_beats_changed, mref))

    def _remove_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        self._listeners.pop('measure:%s:beats' % mref.id).remove()

    def _create_events(
            self, time: audioproc.MusicalTime, measure: pmodel.Measure
    ) -> Iterator[base_track.PianoRollInterval]:
        measure = down_cast(BeatMeasure, measure)
        for beat in measure.beats:
            beat_time = time + beat.time
            event = base_track.PianoRollInterval(
                beat_time, beat_time + audioproc.MusicalDuration(1, 4),
                self._track.pitch, 127)
            yield event

    def __pitch_changed(self, change: model.PropertyChange) -> None:
        self._update_measure_range(0, len(self._track.measure_list))

    def __measure_beats_changed(self, mref: pmodel.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class BeatTrack(pmodel.BeatTrack, base_track.MeasuredTrack):
    measure_cls = BeatMeasure

    def create(
            self, *,
            instrument: Optional[str] = None, pitch: Optional[model.Pitch] = None,
            num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        if instrument is None:
            self.instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=128&preset=0'
        else:
            self.instrument = instrument

        if pitch is None:
            self.pitch = model.Pitch('B2')
        else:
            self.pitch = pitch

        for _ in range(num_measures):
            self.append_measure()

    def create_track_connector(self, **kwargs: Any) -> BeatTrackConnector:
        return BeatTrackConnector(
            track=self,
            node_id=self.event_source_name,
            **kwargs)

    @property
    def event_source_name(self) -> str:
        return '%016x-events' % self.id

    @property
    def instr_name(self) -> str:
        return '%016x-instr' % self.id

    def add_pipeline_nodes(self) -> None:
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        instrument_node = self._pool.create(
            pipeline_graph.InstrumentPipelineGraphNode,
            name="Track Instrument",
            graph_pos=mixer_node.graph_pos - model.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(instrument_node)
        self.instrument_node = instrument_node

        self.project.add_pipeline_graph_connection(self._pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=instrument_node, source_port='out:left',
            dest_node=self.mixer_node, dest_port='in:left'))
        self.project.add_pipeline_graph_connection(self._pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=instrument_node, source_port='out:right',
            dest_node=self.mixer_node, dest_port='in:right'))

        event_source_node = self._pool.create(
            pipeline_graph.PianoRollPipelineGraphNode,
            name="Track Events",
            graph_pos=instrument_node.graph_pos - model.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(event_source_node)
        self.event_source_node = event_source_node

        self.project.add_pipeline_graph_connection(self._pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=event_source_node, source_port='out',
            dest_node=instrument_node, dest_port='in'))

    def remove_pipeline_nodes(self) -> None:
        self.project.remove_pipeline_graph_node(self.event_source_node)
        self.event_source_node = None
        self.project.remove_pipeline_graph_node(self.instrument_node)
        self.instrument_node = None
        super().remove_pipeline_nodes()

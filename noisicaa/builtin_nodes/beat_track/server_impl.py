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

import logging
from typing import Any, MutableSequence, Optional, Iterator, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa.music import commands
from noisicaa.music import pmodel
from noisicaa.music import base_track
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import model as beat_track_model

logger = logging.getLogger(__name__)


class SetBeatTrackPitch(commands.Command):
    proto_type = 'set_beat_track_pitch'
    proto_ext = commands_registry_pb2.set_beat_track_pitch  # type: ignore

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetBeatTrackPitch, pb)
        track = down_cast(BeatTrack, pool[self.proto.command.target])

        track.pitch = model.Pitch.from_proto(pb.pitch)

commands.Command.register_command(SetBeatTrackPitch)


class SetBeatVelocity(commands.Command):
    proto_type = 'set_beat_velocity'
    proto_ext = commands_registry_pb2.set_beat_velocity  # type: ignore

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetBeatVelocity, pb)
        beat = down_cast(Beat, pool[self.proto.command.target])

        beat.velocity = pb.velocity

commands.Command.register_command(SetBeatVelocity)


class AddBeat(commands.Command):
    proto_type = 'add_beat'
    proto_ext = commands_registry_pb2.add_beat  # type: ignore

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddBeat, pb)
        measure = down_cast(BeatMeasure, pool[self.proto.command.target])

        beat = pool.create(
            Beat,
            time=audioproc.MusicalDuration.from_proto(pb.time),
            velocity=100)
        assert audioproc.MusicalDuration(0, 1) <= beat.time < measure.duration
        measure.beats.append(beat)

commands.Command.register_command(AddBeat)


class RemoveBeat(commands.Command):
    proto_type = 'remove_beat'
    proto_ext = commands_registry_pb2.remove_beat  # type: ignore

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemoveBeat, pb)
        measure = down_cast(BeatMeasure, pool[self.proto.command.target])

        beat = down_cast(Beat, pool[pb.beat_id])
        assert beat.is_child_of(measure)
        del measure.beats[beat.index]

commands.Command.register_command(RemoveBeat)


class Beat(pmodel.ProjectChild, beat_track_model.Beat, pmodel.ObjectBase):
    def create(
            self, *,
            time: Optional[audioproc.MusicalDuration] = None,
            velocity: Optional[int] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.velocity = velocity

    @property
    def time(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration.from_proto(self.get_property_value('time'))

    @time.setter
    def time(self, value: audioproc.MusicalDuration) -> None:
        self.set_property_value('time', value.to_proto())

    @property
    def velocity(self) -> int:
        return self.get_property_value('velocity')

    @velocity.setter
    def velocity(self, value: int) -> None:
        self.set_property_value('velocity', value)

    @property
    def measure(self) -> 'BeatMeasure':
        return down_cast(BeatMeasure, super().measure)


class BeatMeasure(base_track.Measure, beat_track_model.BeatMeasure, pmodel.ObjectBase):
    @property
    def beats(self) -> MutableSequence[Beat]:
        return self.get_property_value('beats')

    @property
    def empty(self) -> bool:
        return len(self.beats) == 0


class BeatTrackConnector(base_track.MeasuredTrackConnector):
    _node = None  # type: BeatTrack

    def _add_track_listeners(self) -> None:
        self._listeners['pitch'] = self._node.pitch_changed.add(self.__pitch_changed)

    def _add_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        measure = down_cast(BeatMeasure, mref.measure)
        self._listeners['measure:%s:beats' % mref.id] = measure.content_changed.add(
            lambda _=None: self.__measure_beats_changed(mref))  # type: ignore

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
                self._node.pitch, 127)
            yield event

    def __pitch_changed(self, change: model.PropertyChange) -> None:
        self._update_measure_range(0, len(self._node.measure_list))

    def __measure_beats_changed(self, mref: pmodel.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class BeatTrack(base_track.MeasuredTrack, beat_track_model.BeatTrack, pmodel.ObjectBase):
    measure_cls = BeatMeasure

    def create(
            self, *,
            pitch: Optional[model.Pitch] = None,
            num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        if pitch is None:
            self.pitch = model.Pitch('B2')
        else:
            self.pitch = pitch

        for _ in range(num_measures):
            self.append_measure()

    @property
    def pitch(self) -> model.Pitch:
        return self.get_property_value('pitch')

    @pitch.setter
    def pitch(self, value: model.Pitch) -> None:
        self.set_property_value('pitch', value)

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]) -> BeatTrackConnector:
        return BeatTrackConnector(node=self, message_cb=message_cb)

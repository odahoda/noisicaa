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

from typing import cast, Any, Optional, MutableSequence, Callable, Iterator

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import node_db
from noisicaa import audioproc
from noisicaa import model_base
from noisicaa import value_types
from noisicaa.music import base_track
from noisicaa.music import model
from noisicaa.music import commands
from noisicaa.audioproc.public import musical_time_pb2
from noisicaa.builtin_nodes import commands_registry_pb2
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description
from . import commands_pb2


class UpdateBeatTrack(commands.Command):
    proto_type = 'update_beat_track'
    proto_ext = commands_registry_pb2.update_beat_track

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateBeatTrack, self.pb)
        track = down_cast(BeatTrack, self.pool[pb.track_id])

        if pb.HasField('set_pitch'):
            track.pitch = value_types.Pitch.from_proto(pb.set_pitch)


class CreateBeat(commands.Command):
    proto_type = 'create_beat'
    proto_ext = commands_registry_pb2.create_beat

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateBeat, self.pb)
        measure = down_cast(BeatMeasure, self.pool[pb.measure_id])

        time = audioproc.MusicalDuration.from_proto(pb.time)
        assert audioproc.MusicalDuration(0, 1) <= time < measure.duration

        if pb.HasField('velocity'):
            velocity = pb.velocity
        else:
            velocity = 100

        beat = self.pool.create(
            Beat,
            time=time,
            velocity=velocity)
        measure.beats.append(beat)


class UpdateBeat(commands.Command):
    proto_type = 'update_beat'
    proto_ext = commands_registry_pb2.update_beat

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateBeat, self.pb)
        beat = down_cast(Beat, self.pool[pb.beat_id])

        if pb.HasField('set_velocity'):
            beat.velocity = pb.set_velocity


class DeleteBeat(commands.Command):
    proto_type = 'delete_beat'
    proto_ext = commands_registry_pb2.delete_beat

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteBeat, self.pb)
        beat = down_cast(Beat, self.pool[pb.beat_id])

        measure = beat.measure
        del measure.beats[beat.index]


class BeatTrackConnector(base_track.MeasuredTrackConnector):
    _node = None  # type: BeatTrack

    def _add_track_listeners(self) -> None:
        self._listeners['pitch'] = self._node.pitch_changed.add(self.__pitch_changed)

    def _add_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        measure = down_cast(BeatMeasure, mref.measure)
        self._listeners['measure:%s:beats' % mref.id] = measure.content_changed.add(
            lambda _=None: self.__measure_beats_changed(mref))  # type: ignore

    def _remove_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        self._listeners.pop('measure:%s:beats' % mref.id).remove()

    def _create_events(
            self, time: audioproc.MusicalTime, measure: base_track.Measure
    ) -> Iterator[base_track.PianoRollInterval]:
        measure = down_cast(BeatMeasure, measure)
        for beat in measure.beats:
            beat_time = time + beat.time
            event = base_track.PianoRollInterval(
                beat_time, beat_time + audioproc.MusicalDuration(1, 4),
                self._node.pitch, 127)
            yield event

    def __pitch_changed(self, change: model_base.PropertyChange) -> None:
        self._update_measure_range(0, len(self._node.measure_list))

    def __measure_beats_changed(self, mref: base_track.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class Beat(model.ProjectChild):
    class BeatSpec(model_base.ObjectSpec):
        proto_type = 'beat'
        proto_ext = model_registry_pb2.beat

        time = model_base.ProtoProperty(musical_time_pb2.MusicalDuration)
        velocity = model_base.Property(int)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.time_changed = \
            core.Callback[model_base.PropertyChange[musical_time_pb2.MusicalDuration]]()
        self.velocity_changed = core.Callback[model_base.PropertyChange[int]]()

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
        return cast(BeatMeasure, self.parent)

    def property_changed(self, change: model_base.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class BeatMeasure(base_track.Measure):
    class BeatMeasureSpec(model_base.ObjectSpec):
        proto_type = 'beat_measure'
        proto_ext = model_registry_pb2.beat_measure

        beats = model_base.ObjectListProperty(Beat)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.beats_changed = core.Callback[model_base.PropertyListChange[Beat]]()

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()
        self.beats_changed.add(lambda _: self.content_changed.call())

    @property
    def beats(self) -> MutableSequence[Beat]:
        return self.get_property_value('beats')

    @property
    def empty(self) -> bool:
        return len(self.beats) == 0


class BeatTrack(base_track.MeasuredTrack):
    class BeatTrackSpec(model_base.ObjectSpec):
        proto_type = 'beat_track'
        proto_ext = model_registry_pb2.beat_track

        pitch = model_base.WrappedProtoProperty(value_types.Pitch)

    measure_cls = BeatMeasure

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitch_changed = core.Callback[model_base.PropertyChange[value_types.Pitch]]()

    def create(
            self, *,
            pitch: Optional[value_types.Pitch] = None,
            num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        if pitch is None:
            self.pitch = value_types.Pitch('B2')
        else:
            self.pitch = pitch

        for _ in range(num_measures):
            self.append_measure()

    @property
    def pitch(self) -> value_types.Pitch:
        return self.get_property_value('pitch')

    @pitch.setter
    def pitch(self, value: value_types.Pitch) -> None:
        self.set_property_value('pitch', value)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.BeatTrackDescription

    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> BeatTrackConnector:
        return BeatTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

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

import logging
from typing import Any, MutableSequence, Optional, Iterator, Callable

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


class UpdateBeatTrack(commands.Command):
    proto_type = 'update_beat_track'
    proto_ext = commands_registry_pb2.update_beat_track

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateBeatTrack, self.pb)
        track = down_cast(BeatTrack, self.pool[pb.track_id])

        if pb.HasField('set_pitch'):
            track.pitch = model.Pitch.from_proto(pb.set_pitch)


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
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> BeatTrackConnector:
        return BeatTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

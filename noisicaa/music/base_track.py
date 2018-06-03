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
import random
from typing import Any, Optional, Callable, Iterator, Dict, List, Type  # pylint: disable=unused-import

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import core  # pylint: disable=unused-import
from . import pmodel
from . import pipeline_graph
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class MoveTrack(commands.Command):
    proto_type = 'move_track'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.MoveTrack, pb)
        track = down_cast(pmodel.Track, pool[self.proto.command.target])

        assert not track.is_master_group
        parent = down_cast(pmodel.TrackGroup, track.parent)

        if pb.direction == 0:
            raise ValueError("No direction given.")

        if pb.direction < 0:
            if track.index == 0:
                raise ValueError("Can't move first track up.")
            new_pos = track.index - 1
            del parent.tracks[track.index]
            parent.tracks.insert(new_pos, track)

        elif pb.direction > 0:
            if track.index == len(parent.tracks) - 1:
                raise ValueError("Can't move last track down.")
            new_pos = track.index + 1
            del parent.tracks[track.index]
            parent.tracks.insert(new_pos, track)

commands.Command.register_command(MoveTrack)


class ReparentTrack(commands.Command):
    proto_type = 'reparent_track'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.ReparentTrack, pb)
        track = down_cast(pmodel.Track, pool[self.proto.command.target])

        old_parent = down_cast(pmodel.TrackGroup, track.parent)
        new_parent = down_cast(pmodel.TrackGroup, pool[pb.new_parent])
        assert new_parent.is_child_of(track.project)
        assert isinstance(new_parent, pmodel.TrackGroup)

        assert 0 <= pb.index <= len(new_parent.tracks)

        del old_parent.tracks[track.index]
        new_parent.tracks.insert(pb.index, track)

commands.Command.register_command(ReparentTrack)


class UpdateTrackProperties(commands.Command):
    proto_type = 'update_track_properties'

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.UpdateTrackProperties, pb)
        track = down_cast(pmodel.Track, pool[self.proto.command.target])

        if pb.HasField('name'):
            track.name = pb.name

        if pb.HasField('visible'):
            track.visible = pb.visible

        # TODO: broken, needs to increment generation
        # if pb.HasField('muted'):
        #     track.muted = pb.muted
        #     track.mixer_node.set_control_value('muted', float(pb.muted))

        # if pb.HasField('gain'):
        #     track.gain = pb.gain
        #     track.mixer_node.set_control_value('gain', pb.gain)

        # if pb.HasField('pan'):
        #     track.pan = pb.pan
        #     track.mixer_node.set_control_value('pan', pb.pan)

        if pb.HasField('transpose_octaves'):
            assert isinstance(track, pmodel.ScoreTrack)
            track.transpose_octaves = pb.transpose_octaves

commands.Command.register_command(UpdateTrackProperties)


class TrackConnector(pmodel.TrackConnector):
    def __init__(
            self, *, track: 'Track', message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> None:
        super().__init__()

        self._track = track
        self.__message_cb = message_cb

        self.__initializing = True
        self.__initial_messages = []  # type: List[audioproc.ProcessorMessage]

    def init(self) -> List[audioproc.ProcessorMessage]:
        assert self.__initializing
        self._init_internal()
        self.__initializing = False
        messages = self.__initial_messages
        self.__initial_messages = None
        return messages

    def _init_internal(self) -> None:
        raise NotImplementedError

    def _emit_message(self, msg: audioproc.ProcessorMessage) -> None:
        if self.__initializing:
            self.__initial_messages.append(msg)
        else:
            self.__message_cb(msg)

    def close(self) -> None:
        pass


class Track(pmodel.Track):  # pylint: disable=abstract-method
    def create(self, *, name: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)
        if name is not None:
            self.name = name

    @property
    def parent_audio_sink_name(self) -> str:
        return down_cast(Track, self.parent).mixer_name

    @property
    def parent_audio_sink_node(self) -> pmodel.BasePipelineGraphNode:
        return down_cast(Track, self.parent).mixer_node

    # TODO: the following are common to MeasuredTrack and TrackGroup, but not really
    # generic for all track types.

    @property
    def mixer_name(self) -> str:
        return '%s-track-mixer' % self.id

    @property
    def relative_position_to_parent_audio_out(self) -> model.Pos2F:
        return model.Pos2F(-200, self.index * 100)

    @property
    def default_mixer_name(self) -> str:
        return "Track Mixer"

    def add_pipeline_nodes(self) -> None:
        parent_audio_sink_node = self.parent_audio_sink_node

        project = down_cast(pmodel.Project, self.project)

        mixer_node = self._pool.create(
            pipeline_graph.TrackMixerPipelineGraphNode,
            name=self.default_mixer_name,
            graph_pos=parent_audio_sink_node.graph_pos + self.relative_position_to_parent_audio_out,
            track=self)
        project.add_pipeline_graph_node(mixer_node)
        self.mixer_node = mixer_node

        conn = self._pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=mixer_node, source_port='out:left',
            dest_node=parent_audio_sink_node, dest_port='in:left')
        project.add_pipeline_graph_connection(conn)

        conn = self._pool.create(
            pipeline_graph.PipelineGraphConnection,
            source_node=mixer_node, source_port='out:right',
            dest_node=parent_audio_sink_node, dest_port='in:right')
        project.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self) -> None:
        project = down_cast(pmodel.Project, self.project)
        project.remove_pipeline_graph_node(self.mixer_node)
        self.mixer_node = None


class Measure(pmodel.Measure):
    @property
    def empty(self) -> bool:
        return False


class MeasureReference(pmodel.MeasureReference):
    def create(self, *, measure: Optional[Measure] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.measure = measure


class PianoRollInterval(object):
    def __init__(
            self, begin: audioproc.MusicalTime, end: audioproc.MusicalTime,
            pitch: model.Pitch, velocity: int) -> None:
        self.id = random.getrandbits(64)
        self.begin = begin
        self.end = end
        self.pitch = pitch
        self.velocity = velocity

    def __str__(self) -> str:
        return '<PianoRollInterval id=%016x begin=%s end=%s pitch=%s velocity=%s>' % (
            self.id, self.begin, self.end, self.pitch, self.velocity)
    __repr__ = __str__

    def create_add_message(self, node_id: str) -> audioproc.ProcessorMessage:
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_add_interval=audioproc.ProcessorMessage.PianoRollAddInterval(
                id=self.id,
                start_time=self.begin.to_proto(),
                end_time=self.end.to_proto(),
                pitch=self.pitch.midi_note,
                velocity=self.velocity))

    def create_remove_message(self, node_id: str) -> audioproc.ProcessorMessage:
        return audioproc.ProcessorMessage(
            node_id=node_id,
            pianoroll_remove_interval=audioproc.ProcessorMessage.PianoRollRemoveInterval(
                id=self.id))


class MeasuredTrackConnector(TrackConnector):
    _track = None  # type: MeasuredTrack

    def __init__(self, *, node_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._listeners = {}  # type: Dict[str, core.Listener]

        self.__node_id = node_id
        self.__measure_events = {}  # type: Dict[int, List[PianoRollInterval]]

    def _init_internal(self) -> None:
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            self.__add_measure(time, mref)
            time += mref.measure.duration

        self._listeners['measure_list'] = self._track.measure_list_changed.add(
            self.__measure_list_changed)
        self._add_track_listeners()

    def close(self) -> None:
        for listener in self._listeners.values():
            listener.remove()
        self._listeners.clear()

        super().close()

    def __add_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_add_message(self.__node_id))

    def __remove_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_remove_message(self.__node_id))

    def _add_track_listeners(self) -> None:
        pass

    def _add_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        pass

    def _remove_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        pass

    def _create_events(
            self, time: audioproc.MusicalTime, measure: pmodel.Measure
    ) -> Iterator[PianoRollInterval]:
        raise NotImplementedError

    def _update_measure(self, time: audioproc.MusicalTime, mref: pmodel.MeasureReference) -> None:
        events = self.__measure_events[mref.id]
        for event in events:
            self.__remove_event(event)
        events.clear()
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

    def _update_measure_range(
            self, begin: audioproc.MusicalTime, end: audioproc.MusicalTime) -> None:
        time = audioproc.MusicalTime()
        for mref in self._track.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(time, mref)

            time += mref.measure.duration

    def __measure_list_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyListInsert):
            time = audioproc.MusicalTime()
            for mref in self._track.measure_list:
                if mref.index == change.new_value.index:
                    assert mref is change.new_value
                    self.__add_measure(time, mref)
                elif mref.index > change.new_value.index:
                    self._update_measure(time, mref)

                time += mref.measure.duration

        elif isinstance(change, model.PropertyListDelete):
            mref = change.old_value
            self.__remove_measure(mref)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_measure(self, time: audioproc.MusicalTime, mref: pmodel.MeasureReference) -> None:
        assert mref.id not in self.__measure_events

        events = self.__measure_events[mref.id] = []
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

        self._listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda _: self.__measure_changed(mref))
        self._add_measure_listeners(mref)

    def __remove_measure(self, mref: pmodel.MeasureReference) -> None:
        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        for event in self.__measure_events.pop(mref.id):
            self.__remove_event(event)

    def __measure_changed(self, mref: pmodel.MeasureReference) -> None:
        self._remove_measure_listeners(mref)
        self._listeners.pop('measure:%s:ref' % mref.id).remove()

        self._listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda _: self.__measure_changed(mref))
        self._add_measure_listeners(mref)

        self._update_measure_range(mref.index, mref.index + 1)


class MeasuredTrack(pmodel.MeasuredTrack, Track):  # pylint: disable=abstract-method
    measure_cls = None  # type: Type[Measure]

    def append_measure(self) -> None:
        self.insert_measure(-1)

    def insert_measure(self, idx: int) -> None:
        assert idx == -1 or (0 <= idx <= len(self.measure_list) - 1)

        if idx == -1:
            idx = len(self.measure_list)

        if idx == 0 and len(self.measure_list) > 0:
            ref = self.measure_list[0].measure
        elif idx > 0:
            ref = self.measure_list[idx-1].measure
        else:
            ref = None

        measure = self.create_empty_measure(ref)
        self.measure_heap.append(measure)
        self.measure_list.insert(idx, self._pool.create(MeasureReference, measure=measure))

    def garbage_collect_measures(self) -> None:
        ref_counts = {measure.id: 0 for measure in self.measure_heap}

        for mref in self.measure_list:
            ref_counts[mref.measure.id] += 1

        measure_ids_to_delete = [
            measure_id for measure_id, ref_count in ref_counts.items()
            if ref_count == 0]
        indices_to_delete = [
            self._pool[measure_id].index
            for measure_id in measure_ids_to_delete]
        for idx in sorted(indices_to_delete, reverse=True):
            del self.measure_heap[idx]

    def remove_measure(self, idx: int) -> None:
        del self.measure_list[idx]
        self.garbage_collect_measures()

    def create_empty_measure(self, ref: Optional[pmodel.Measure]) -> Measure:  # pylint: disable=unused-argument
        return self._pool.create(self.measure_cls)

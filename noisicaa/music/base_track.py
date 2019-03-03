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

import itertools
import logging
import random
from typing import cast, Any, Optional, Iterator, Dict, List, Type

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa import core
from noisicaa.builtin_nodes.pianoroll import processor_messages as pianoroll
from . import node_connector
from . import graph
from . import pmodel
from . import commands
from . import commands_pb2

logger = logging.getLogger(__name__)


class UpdateTrack(commands.Command):
    proto_type = 'update_track'

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateTrack, self.pb)
        track = down_cast(pmodel.Track, self.pool[pb.track_id])

        if pb.HasField('set_visible'):
            track.visible = pb.set_visible

        if pb.HasField('set_list_position'):
            track.list_position = pb.set_list_position


class CreateMeasure(commands.Command):
    proto_type = 'create_measure'

    def run(self) -> None:
        pb = down_cast(commands_pb2.CreateMeasure, self.pb)
        track = down_cast(pmodel.MeasuredTrack, self.pool[pb.track_id])

        track.insert_measure(pb.pos)


class UpdateMeasure(commands.Command):
    proto_type = 'update_measure'

    def run(self) -> None:
        pb = down_cast(commands_pb2.UpdateMeasure, self.pb)
        mref = down_cast(pmodel.MeasureReference, self.pool[pb.measure_id])
        track = cast(MeasuredTrack, mref.track)

        if pb.HasField('clear'):
            measure = track.create_empty_measure(mref.measure)
            track.measure_heap.append(measure)
            mref.measure = measure

        if pb.HasField('set_time_signature'):
            mref.measure.time_signature = model.TimeSignature.from_proto(pb.set_time_signature)

        track.garbage_collect_measures()


class DeleteMeasure(commands.Command):
    proto_type = 'delete_measure'

    def run(self) -> None:
        pb = down_cast(commands_pb2.DeleteMeasure, self.pb)
        mref = down_cast(pmodel.MeasureReference, self.pool[pb.measure_id])
        track = mref.track
        track.remove_measure(mref.index)


class PasteMeasures(commands.Command):
    proto_type = 'paste_measures'

    def run(self) -> None:
        pb = down_cast(commands_pb2.PasteMeasures, self.pb)

        target_measures = [
            cast(pmodel.MeasureReference, self.pool[obj_id])
            for obj_id in pb.target_ids]
        assert all(isinstance(obj, pmodel.MeasureReference) for obj in target_measures)

        affected_track_ids = set(obj.track.id for obj in target_measures)
        assert len(affected_track_ids) == 1

        if pb.mode == 'link':
            for target, src_proto in zip(target_measures, itertools.cycle(pb.src_objs)):
                src = down_cast(pmodel.Measure, self.pool[src_proto.root])
                assert src.is_child_of(target.track)
                target.measure = src

        elif pb.mode == 'overwrite':
            measure_map = {}  # type: Dict[int, pmodel.Measure]
            for target, src_proto in zip(target_measures, itertools.cycle(pb.src_objs)):
                try:
                    measure = measure_map[src_proto.root]
                except KeyError:
                    measure = down_cast(pmodel.Measure, self.pool.clone_tree(src_proto))
                    measure_map[src_proto.root] = measure
                    cast(pmodel.MeasuredTrack, target.track).measure_heap.append(measure)

                target.measure = measure

        else:
            raise ValueError(pb.mode)

        for track_id in affected_track_ids:
            cast(pmodel.MeasuredTrack, self.pool[track_id]).garbage_collect_measures()


class Track(pmodel.Track, graph.BaseNode):  # pylint: disable=abstract-method
    # TODO: the following are common to MeasuredTrack and TrackGroup, but not really
    # generic for all track types.

    @property
    def relative_position_to_parent_audio_out(self) -> model.Pos2F:
        return model.Pos2F(-200, self.index * 100)


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
        return pianoroll.add_interval(
            node_id=node_id,
            id=self.id,
            start_time=self.begin,
            end_time=self.end,
            pitch=self.pitch.midi_note,
            velocity=self.velocity)

    def create_remove_message(self, node_id: str) -> audioproc.ProcessorMessage:
        return pianoroll.remove_interval(
            node_id=node_id,
            id=self.id)


class MeasuredTrackConnector(node_connector.NodeConnector):
    _node = None  # type: MeasuredTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._listeners = {}  # type: Dict[str, core.Listener]

        self.__node_id = self._node.pipeline_node_id
        self.__measure_events = {}  # type: Dict[int, List[PianoRollInterval]]

    def _init_internal(self) -> None:
        time = audioproc.MusicalTime()
        for mref in self._node.measure_list:
            self.__add_measure(time, mref)
            time += mref.measure.duration

        self._listeners['measure_list'] = self._node.measure_list_changed.add(
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
        for mref in self._node.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(time, mref)

            time += mref.measure.duration

    def __measure_list_changed(self, change: model.PropertyChange) -> None:
        if isinstance(change, model.PropertyListInsert):
            time = audioproc.MusicalTime()
            for mref in self._node.measure_list:
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

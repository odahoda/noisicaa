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
from typing import cast, Any, Optional, Iterator, Dict, List, Set, Type

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa import core
from noisicaa.builtin_nodes.pianoroll import processor_messages as pianoroll
from . import model_base
from . import _model
from . import node_connector
from . import graph
from . import base_track_pb2

logger = logging.getLogger(__name__)


class Track(_model.Track, graph.BaseNode):  # pylint: disable=abstract-method
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.duration_changed = core.Callback[None]()

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return audioproc.MusicalDuration(1, 1)


class Measure(_model.Measure, model_base.ProjectChild):
    @property
    def track(self) -> 'MeasuredTrack':
        return cast(MeasuredTrack, self.parent)

    @property
    def duration(self) -> audioproc.MusicalDuration:
        time_signature = self.get_property_value('time_signature')
        return audioproc.MusicalDuration(time_signature.upper, time_signature.lower)

    @property
    def empty(self) -> bool:
        return False


class MeasureReference(_model.MeasureReference, model_base.ProjectChild):
    def create(self, *, measure: Optional[Measure] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.measure = measure

    @property
    def track(self) -> 'MeasuredTrack':
        return cast(MeasuredTrack, self.parent)

    @property
    def prev_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().prev_sibling)

    @property
    def next_sibling(self) -> 'MeasureReference':
        return down_cast(MeasureReference, super().next_sibling)

    def clear_measure(self) -> None:
        track = self.track
        measure = track.create_empty_measure(self.measure)
        track.measure_heap.append(measure)
        self.measure = measure
        track.garbage_collect_measures()


class PianoRollInterval(object):
    def __init__(
            self, begin: audioproc.MusicalTime, end: audioproc.MusicalTime,
            pitch: value_types.Pitch, velocity: int) -> None:
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

        self._listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self._listeners.cleanup)

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

    def __add_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_add_message(self.__node_id))

    def __remove_event(self, event: PianoRollInterval) -> None:
        self._emit_message(event.create_remove_message(self.__node_id))

    def _add_track_listeners(self) -> None:
        pass

    def _add_measure_listeners(self, mref: MeasureReference) -> None:
        pass

    def _remove_measure_listeners(self, mref: MeasureReference) -> None:
        pass

    def _create_events(
            self, time: audioproc.MusicalTime, measure: Measure
    ) -> Iterator[PianoRollInterval]:
        raise NotImplementedError

    def _update_measure(self, time: audioproc.MusicalTime, mref: MeasureReference) -> None:
        events = self.__measure_events[mref.id]
        for event in events:
            self.__remove_event(event)
        events.clear()
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

    def _update_measure_range(self, begin: int, end: int) -> None:
        time = audioproc.MusicalTime()
        for mref in self._node.measure_list:
            if mref.index >= end:
                break

            if mref.index >= begin:
                self._update_measure(time, mref)

            time += mref.measure.duration

    def __measure_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            time = audioproc.MusicalTime()
            for mref in self._node.measure_list:
                if mref.index == change.new_value.index:
                    assert mref is change.new_value
                    self.__add_measure(time, mref)
                elif mref.index > change.new_value.index:
                    self._update_measure(time, mref)

                time += mref.measure.duration

        elif isinstance(change, model_base.PropertyListDelete):
            mref = change.old_value
            self.__remove_measure(mref)
        else:
            raise TypeError(
                "Unsupported change type %s" % type(change))

    def __add_measure(self, time: audioproc.MusicalTime, mref: MeasureReference) -> None:
        assert mref.id not in self.__measure_events

        events = self.__measure_events[mref.id] = []
        for event in self._create_events(time, mref.measure):
            self.__add_event(event)
            events.append(event)

        self._listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda _: self.__measure_changed(mref))
        self._add_measure_listeners(mref)

    def __remove_measure(self, mref: MeasureReference) -> None:
        self._remove_measure_listeners(mref)
        del self._listeners['measure:%s:ref' % mref.id]

        for event in self.__measure_events.pop(mref.id):
            self.__remove_event(event)

    def __measure_changed(self, mref: MeasureReference) -> None:
        self._remove_measure_listeners(mref)
        del self._listeners['measure:%s:ref' % mref.id]

        self._listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda _: self.__measure_changed(mref))
        self._add_measure_listeners(mref)

        self._update_measure_range(mref.index, mref.index + 1)


class MeasuredTrack(_model.MeasuredTrack, Track):  # pylint: disable=abstract-method
    measure_cls = None  # type: Type[Measure]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = {}  # type: Dict[str, core.Listener]

    def setup(self) -> None:
        super().setup()

        for mref in self.measure_list:
            self.__add_measure(mref)

        self.measure_list_changed.add(self.__measure_list_changed)

    def __measure_list_changed(self, change: model_base.PropertyChange) -> None:
        if isinstance(change, model_base.PropertyListInsert):
            self.__add_measure(change.new_value)
        elif isinstance(change, model_base.PropertyListDelete):
            self.__remove_measure(change.old_value)
        else:
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_measure(self, mref: MeasureReference) -> None:
        self.__listeners['measure:%s:ref' % mref.id] = mref.measure_changed.add(
            lambda *_: self.__measure_changed(mref))
        self.duration_changed.call()

    def __remove_measure(self, mref: MeasureReference) -> None:
        self.__listeners.pop('measure:%s:ref' % mref.id).remove()
        self.duration_changed.call()

    def __measure_changed(self, mref: MeasureReference) -> None:
        self.duration_changed.call()

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = audioproc.MusicalDuration()
        for mref in self.measure_list:
            duration += mref.measure.duration
        return duration

    def append_measure(self) -> Measure:
        return self.insert_measure(-1)

    def insert_measure(self, idx: int) -> Measure:
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

        return measure

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

    def create_empty_measure(self, ref: Optional[Measure]) -> Measure:  # pylint: disable=unused-argument
        return self._pool.create(self.measure_cls)

    def copy_measures(self, refs: List[MeasureReference]) -> base_track_pb2.Measures:
        data = base_track_pb2.Measures()

        measure_ids = set()  # type: Set[int]
        for ref in refs:
            measure = ref.measure
            if measure.id not in measure_ids:
                serialized_measure = data.measures.add()
                serialized_measure.CopyFrom(measure.serialize())
                measure_ids.add(measure.id)

            serialized_ref = data.refs.add()
            serialized_ref.measure = measure.id

        return data

    def paste_measures(
            self, data: base_track_pb2.Measures, first_index: int, last_index: int
    ) -> None:
        assert first_index <= last_index
        assert last_index < len(self.measure_list)

        measure_map = {}  # type: Dict[int, int]
        for index, serialized_measure in enumerate(data.measures):
            measure_map[serialized_measure.root] = index

        for serialized_ref, index in zip(
                itertools.cycle(data.refs), range(first_index, last_index + 1)):
            measure = self._pool.clone_tree(data.measures[measure_map[serialized_ref.measure]])
            self.measure_heap.append(measure)

            ref = self.measure_list[index]
            ref.measure = measure

        self.garbage_collect_measures()

    def link_measures(
            self, data: base_track_pb2.Measures, first_index: int, last_index: int
    ) -> None:
        assert first_index <= last_index
        assert last_index < len(self.measure_list)

        existing_measures = {measure.id: measure for measure in self.measure_heap}

        for serialized_ref, index in zip(
                itertools.cycle(data.refs), range(first_index, last_index + 1)):
            assert serialized_ref.measure in existing_measures
            ref = self.measure_list[index]
            ref.measure = existing_measures[serialized_ref.measure]

        self.garbage_collect_measures()

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

import bisect
import functools
import logging
from typing import Any, Callable, Iterator, Dict, Tuple

from noisicaa import audioproc
from noisicaa import core
from noisicaa import music
from noisicaa import node_db
from noisicaa import value_types
from noisicaa.music import node_connector
from . import node_description
from . import processor_messages
from . import _model

logger = logging.getLogger(__name__)


class PianoRollTrackConnector(node_connector.NodeConnector):
    _node = None  # type: PianoRollTrack

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = core.ListenerMap[str]()
        self.add_cleanup_function(self.__listeners.cleanup)

    def _init_internal(self) -> None:
        for segment in self._node.segment_heap:
            self.__add_segment(segment)
        self.__listeners['segment_heap'] = self._node.segment_heap_changed.add(
            self.__segment_heap_changed)

        for segment_ref in self._node.segments:
            self.__add_segment_ref(segment_ref)
        self.__listeners['segments'] = self._node.segments_changed.add(
            self.__segments_changed)

    def __segment_heap_changed(self, change: music.PropertyListChange['PianoRollSegment']) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__add_segment(change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__remove_segment(change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_segment(self, segment: 'PianoRollSegment') -> None:
        self._emit_message(processor_messages.add_segment(
            track=self._node,
            segment=segment))

        self.__listeners['%s:duration' % segment.id] = segment.duration_changed.add(
            functools.partial(self.__duration_changed, segment))

        for event in segment.events:
            self.__add_event(segment, event)
        self.__listeners['%s:events' % segment.id] = segment.events_changed.add(
            functools.partial(self.__events_changed, segment))

    def __remove_segment(self, segment: 'PianoRollSegment') -> None:
        self._emit_message(processor_messages.remove_segment(
            track=self._node,
            segment=segment))

        del self.__listeners['%s:events' % segment.id]
        del self.__listeners['%s:duration' % segment.id]

    def __duration_changed(
            self,
            segment: 'PianoRollSegment',
            change: music.PropertyValueChange[audioproc.MusicalDuration]
    ) -> None:
        self._emit_message(processor_messages.update_segment(
            track=self._node,
            segment=segment))

    def __events_changed(
            self,
            segment: 'PianoRollSegment',
            change: music.PropertyListChange['PianoRollEvent']
    ) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__add_event(segment, change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__remove_event(segment, change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_event(self, segment: 'PianoRollSegment', event: 'PianoRollEvent') -> None:
        self._emit_message(processor_messages.add_event(
            track=self._node,
            segment=segment,
            event=event))

    def __remove_event(self, segment: 'PianoRollSegment', event: 'PianoRollEvent') -> None:
        self._emit_message(processor_messages.remove_event(
            track=self._node,
            segment=segment,
            event=event))

    def __segments_changed(self, change: music.PropertyListChange['PianoRollSegmentRef']) -> None:
        if isinstance(change, music.PropertyListInsert):
            self.__add_segment_ref(change.new_value)

        elif isinstance(change, music.PropertyListDelete):
            self.__remove_segment_ref(change.old_value)

        else:  # pragma: no coverage
            raise TypeError("Unsupported change type %s" % type(change))

    def __add_segment_ref(self, segment_ref: 'PianoRollSegmentRef') -> None:
        self._emit_message(processor_messages.add_segment_ref(
            track=self._node,
            segment_ref=segment_ref))

        self.__listeners['%s:time' % segment_ref.id] = segment_ref.time_changed.add(
            functools.partial(self.__time_changed, segment_ref))

    def __remove_segment_ref(self, segment_ref: 'PianoRollSegmentRef') -> None:
        self._emit_message(processor_messages.remove_segment_ref(
            track=self._node,
            segment_ref=segment_ref))

        del self.__listeners['%s:time' % segment_ref.id]

    def __time_changed(
            self,
            segment_ref: 'PianoRollSegmentRef',
            change: music.PropertyValueChange[audioproc.MusicalTime]
    ) -> None:
        self._emit_message(processor_messages.update_segment_ref(
            track=self._node,
            segment_ref=segment_ref))


class PianoRollEvent(_model.PianoRollEvent):
    def create(self, *, midi_event: value_types.MidiEvent, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.midi_event = midi_event

    @property
    def is_note_on(self) -> bool:
        return self.midi_event.is_note_on

    @property
    def is_note_off(self) -> bool:
        return self.midi_event.is_note_off

    @property
    def time(self) -> audioproc.MusicalTime:
        return self.midi_event.time

    @property
    def channel(self) -> int:
        return self.midi_event.channel

    @property
    def pitch(self) -> int:
        return self.midi_event.pitch

    @property
    def velocity(self) -> int:
        return self.midi_event.velocity

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event == other.midi_event

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event != other.midi_event

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event > other.midi_event

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event >= other.midi_event

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event < other.midi_event

    def __le__(self, other: object) -> bool:
        if not isinstance(other, PianoRollEvent):
            raise TypeError
        return self.midi_event <= other.midi_event


class Interval(object):
    __slots__ = ['start_event', 'end_event', '__duration']

    def __init__(
            self, *,
            start_event: PianoRollEvent,
            end_event: PianoRollEvent = None,
            duration: audioproc.MusicalDuration = None) -> None:
        assert start_event.is_note_on
        self.start_event = start_event
        if end_event is not None:
            assert end_event.is_note_off
            assert duration is None
            self.end_event = end_event
            self.__duration = self.end_event.time - self.start_event.time
        else:
            assert end_event is None
            assert duration is not None
            self.end_event = None
            self.__duration = duration

    @property
    def start_time(self) -> audioproc.MusicalTime:
        return self.start_event.time

    @property
    def end_time(self) -> audioproc.MusicalTime:
        return self.start_event.time + self.__duration

    @property
    def duration(self) -> audioproc.MusicalDuration:
        return self.__duration


class PianoRollSegment(_model.PianoRollSegment):
    def create(self, *, duration: audioproc.MusicalDuration, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.duration = duration

    def add_event(self, midi_event: value_types.MidiEvent) -> PianoRollEvent:
        event = self._pool.create(PianoRollEvent, midi_event=midi_event)
        index = bisect.bisect(self.events, event)
        self.events.insert(index, event)
        return event

    def remove_event(self, event: PianoRollEvent) -> None:
        del self.events[event.index]

    def intervals(self) -> Iterator[Interval]:
        active_pitches = {}  # type: Dict[Tuple[int, int], PianoRollEvent]
        for event in self.events:
            assert event.is_note_on or event.is_note_off

            k = (event.channel, event.pitch)

            if k in active_pitches:
                start_event = active_pitches.pop(k)
                if event.is_note_off:
                    yield Interval(
                        start_event=start_event,
                        end_event=event)
                else:
                    yield Interval(
                        start_event=start_event,
                        duration=event.time - start_event.time)

            if event.is_note_on:
                active_pitches[k] = event

        end_time = self.duration.as_time()
        for event in active_pitches.values():
            yield Interval(
                start_event=event,
                duration=end_time - event.time)


class PianoRollSegmentRef(_model.PianoRollSegmentRef):
    def create(
            self, *,
            time: audioproc.MusicalTime,
            segment: PianoRollSegment,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.time = time
        self.segment = segment


class PianoRollTrack(_model.PianoRollTrack):
    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> PianoRollTrackConnector:
        return PianoRollTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.PianoRollTrackDescription

    def __garbage_collect_segments(self) -> None:
        ref_counts = {segment.id: 0 for segment in self.segment_heap}

        for segment_ref in self.segments:
            ref_counts[segment_ref.segment.id] += 1

        segment_ids_to_delete = [
            segment_id for segment_id, ref_count in ref_counts.items()
            if ref_count == 0]
        indices_to_delete = [
            self._pool[segment_id].index
            for segment_id in segment_ids_to_delete]
        for idx in sorted(indices_to_delete, reverse=True):
            del self.segment_heap[idx]

    def create_segment(
            self,
            time: audioproc.MusicalTime,
            duration: audioproc.MusicalDuration
    ) -> PianoRollSegmentRef:
        segment = self._pool.create(PianoRollSegment, duration=duration)
        self.segment_heap.append(segment)

        ref = self._pool.create(PianoRollSegmentRef, time=time, segment=segment)
        self.segments.append(ref)

        return ref

    def remove_segment(self, segment_ref: PianoRollSegmentRef) -> None:
        assert segment_ref.parent is self
        del self.segments[segment_ref.index]
        self.__garbage_collect_segments()

    def split_segment(
            self,
            segment_ref: PianoRollSegmentRef,
            split_time: audioproc.MusicalTime
    ) -> None:
        assert segment_ref.parent is self

        start_time = segment_ref.time
        end_time = start_time + segment_ref.segment.duration

        segment1 = segment_ref.segment
        segment1.duration = split_time - start_time
        segment_ref2 = self.create_segment(split_time, end_time - split_time)
        segment2 = segment_ref2.segment

        intervals = list(segment1.intervals())
        rel_split_time = split_time.relative_to(start_time)

        for interval in intervals:
            if interval.end_time <= rel_split_time:
                # remains in segment1
                pass

            elif interval.start_time >= rel_split_time:
                # move completely to segment2
                segment2.add_event(interval.start_event.midi_event.relative_to(rel_split_time))
                segment1.remove_event(interval.start_event)
                if interval.end_event is not None:
                    segment2.add_event(interval.end_event.midi_event.relative_to(rel_split_time))
                    segment1.remove_event(interval.end_event)

            else:
                # split interval
                segment2.add_event(value_types.MidiEvent(
                    audioproc.MusicalTime(0, 1), interval.start_event.midi_event.midi))
                if interval.end_event is not None:
                    segment2.add_event(interval.end_event.midi_event.relative_to(rel_split_time))
                    segment1.add_event(value_types.MidiEvent(
                        rel_split_time, interval.end_event.midi_event.midi))
                    segment1.remove_event(interval.end_event)

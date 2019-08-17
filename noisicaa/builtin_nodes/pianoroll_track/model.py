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
from typing import Any, Callable

from noisicaa import audioproc
from noisicaa import node_db
from noisicaa.music import node_connector
from . import node_description
from . import _model

logger = logging.getLogger(__name__)


class PianoRollTrackConnector(node_connector.NodeConnector):
    _node = None  # type: PianoRollTrack

    def _init_internal(self) -> None:
        pass


class PianoRollSegment(_model.PianoRollSegment):
    def create(self, *, duration: audioproc.MusicalDuration, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.duration = duration


class PianoRollSegmentRef(_model.PianoRollSegmentRef):
    def create(self, *, time: audioproc.MusicalTime, segment: PianoRollSegment, **kwargs: Any) -> None:
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

    def create_segment(self, time: audioproc.MusicalTime, duration: audioproc.MusicalDuration) -> PianoRollSegmentRef:
        segment = self._pool.create(PianoRollSegment, duration=duration)
        self.segment_heap.append(segment)

        ref = self._pool.create(PianoRollSegmentRef, time=time, segment=segment)
        self.segments.append(ref)

        return ref

    def remove_segment(self, segment_ref: PianoRollSegmentRef) -> None:
        assert segment_ref.parent is self
        del self.segments[segment_ref.index]
        self.__garbage_collect_segments()

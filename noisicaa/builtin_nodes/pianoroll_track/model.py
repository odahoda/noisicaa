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

import fractions
import logging
from typing import cast, Any, Optional, Iterator, Iterable, Callable

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import audioproc
from noisicaa import value_types
from noisicaa import node_db
from noisicaa import music
from noisicaa.music import base_track
from noisicaa.music import node_connector
from . import node_description
from . import _model

logger = logging.getLogger(__name__)


class PianoRollTrackConnector(node_connector.NodeConnector):
    _node = None  # type: PianoRollTrack

    # def _add_track_listeners(self) -> None:
    #     self._listeners['transpose_octaves'] = self._node.transpose_octaves_changed.add(
    #         self.__transpose_octaves_changed)

    # def _add_measure_listeners(self, mref: base_track.MeasureReference) -> None:
    #     measure = down_cast(ScoreMeasure, mref.measure)
    #     self._listeners['measure:%s:notes' % mref.id] = measure.content_changed.add(
    #         lambda _=None: self.__measure_notes_changed(mref))  # type: ignore

    # def _remove_measure_listeners(self, mref: base_track.MeasureReference) -> None:
    #     del self._listeners['measure:%s:notes' % mref.id]

    # def _create_events(
    #         self, time: audioproc.MusicalTime, measure: base_track.Measure
    # ) -> Iterator[base_track.PianoRollInterval]:
    #     measure = down_cast(ScoreMeasure, measure)
    #     for note in measure.notes:
    #         if not note.is_rest:
    #             for pitch in note.pitches:
    #                 pitch = pitch.transposed(octaves=self._node.transpose_octaves)
    #                 event = base_track.PianoRollInterval(
    #                     time, time + note.duration, pitch, 127)
    #                 yield event

    #         time += note.duration

    # def __transpose_octaves_changed(self, change: music.PropertyChange) -> None:
    #     self._update_measure_range(0, len(self._node.measure_list))

    # def __measure_notes_changed(self, mref: base_track.MeasureReference) -> None:
    #     self._update_measure_range(mref.index, mref.index + 1)


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

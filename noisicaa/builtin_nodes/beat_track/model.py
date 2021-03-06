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

from typing import cast, Any, Optional, Callable, Iterator

from noisicaa.core.typing_extra import down_cast
from noisicaa import core
from noisicaa import node_db
from noisicaa import audioproc
from noisicaa import music
from noisicaa import value_types
from noisicaa.music import base_track
from . import node_description
from . import _model


class BeatTrackConnector(base_track.MeasuredTrackConnector):
    _node = None  # type: BeatTrack

    def _add_track_listeners(self) -> None:
        self._listeners['pitch'] = self._node.pitch_changed.add(self.__pitch_changed)

    def _add_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        measure = down_cast(BeatMeasure, mref.measure)
        self._listeners['measure:%s:beats' % mref.id] = measure.content_changed.add(
            lambda _=None: self.__measure_beats_changed(mref))  # type: ignore[misc]

    def _remove_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        del self._listeners['measure:%s:beats' % mref.id]

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

    def __pitch_changed(self, change: music.PropertyChange) -> None:
        self._update_measure_range(0, len(self._node.measure_list))

    def __measure_beats_changed(self, mref: base_track.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class Beat(_model.Beat):
    def create(
            self, *,
            time: Optional[audioproc.MusicalDuration] = None,
            velocity: Optional[int] = None,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        self.time = time
        self.velocity = velocity

    @property
    def measure(self) -> 'BeatMeasure':
        return cast(BeatMeasure, self.parent)

    def property_changed(self, change: music.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class BeatMeasure(_model.BeatMeasure):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()
        self.beats_changed.add(lambda _: self.content_changed.call())

    @property
    def empty(self) -> bool:
        return len(self.beats) == 0

    def create_beat(self, time: audioproc.MusicalDuration, velocity: int = 100) -> Beat:
        assert audioproc.MusicalDuration(0, 1) <= time < self.duration
        assert 0 <= velocity <= 127
        beat = self._pool.create(
            Beat,
            time=time,
            velocity=velocity)
        self.beats.append(beat)
        return beat

    def delete_beat(self, beat: Beat) -> None:
        del self.beats[beat.index]


class BeatTrack(_model.BeatTrack):
    measure_cls = BeatMeasure

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
    def description(self) -> node_db.NodeDescription:
        return node_description.BeatTrackDescription

    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> BeatTrackConnector:
        return BeatTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

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
from . import node_description
from . import _model

logger = logging.getLogger(__name__)


class ScoreTrackConnector(base_track.MeasuredTrackConnector):
    _node = None  # type: ScoreTrack

    def _add_track_listeners(self) -> None:
        self._listeners['transpose_octaves'] = self._node.transpose_octaves_changed.add(
            self.__transpose_octaves_changed)

    def _add_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        measure = down_cast(ScoreMeasure, mref.measure)
        self._listeners['measure:%s:notes' % mref.id] = measure.content_changed.add(
            lambda _=None: self.__measure_notes_changed(mref))  # type: ignore[misc]

    def _remove_measure_listeners(self, mref: base_track.MeasureReference) -> None:
        del self._listeners['measure:%s:notes' % mref.id]

    def _create_events(
            self, time: audioproc.MusicalTime, measure: base_track.Measure
    ) -> Iterator[base_track.PianoRollInterval]:
        measure = down_cast(ScoreMeasure, measure)
        for note in measure.notes:
            if not note.is_rest:
                for pitch in note.pitches:
                    pitch = pitch.transposed(octaves=self._node.transpose_octaves)
                    event = base_track.PianoRollInterval(
                        time, time + note.duration, pitch, 127)
                    yield event

            time += note.duration

    def __transpose_octaves_changed(self, change: music.PropertyChange) -> None:
        self._update_measure_range(0, len(self._node.measure_list))

    def __measure_notes_changed(self, mref: base_track.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class Note(_model.Note):
    def __str__(self) -> str:
        n = ''
        if len(self.pitches) == 1:
            n += str(self.pitches[0])
        else:
            n += '[' + ''.join(str(p) for p in self.pitches) + ']'

        duration = self.duration
        if duration.numerator == 1:
            n += '/%d' % duration.denominator
        elif duration.denominator == 1:
            n += ';%d' % duration.numerator
        else:
            n += ';%d/%d' % (duration.numerator, duration.denominator)

        return n

    def create(
            self, *,
            pitches: Optional[Iterable[value_types.Pitch]] = None,
            base_duration: Optional[audioproc.MusicalDuration] = None,
            dots: int = 0, tuplet: int = 0,
            **kwargs: Any) -> None:
        super().create(**kwargs)

        if pitches is not None:
            self.pitches.extend(pitches)
        if base_duration is None:
            base_duration = audioproc.MusicalDuration(1, 4)
        self.base_duration = base_duration
        self.dots = dots
        self.tuplet = tuplet

        assert (self.base_duration.numerator == 1
                and self.base_duration.denominator in (1, 2, 4, 8, 16, 32)), \
            self.base_duration

    def _set_dots(self, value: int) -> None:
        if value > self.max_allowed_dots:
            raise ValueError("Too many dots on note")

        super()._set_dots(value)

    def _set_tuplet(self, value: int) -> None:
        if value not in (0, 3, 5):
            raise ValueError("Invalid tuplet type")

        super()._set_tuplet(value)

    @property
    def measure(self) -> 'ScoreMeasure':
        return cast(ScoreMeasure, self.parent)

    @property
    def is_rest(self) -> bool:
        pitches = self.pitches
        return len(pitches) == 1 and pitches[0].is_rest

    @property
    def max_allowed_dots(self) -> int:
        base_duration = self.base_duration
        if base_duration <= audioproc.MusicalDuration(1, 32):
            return 0
        if base_duration <= audioproc.MusicalDuration(1, 16):
            return 1
        if base_duration <= audioproc.MusicalDuration(1, 8):
            return 2
        return 3

    @property
    def duration(self) -> audioproc.MusicalDuration:
        duration = self.base_duration
        dots = self.dots
        tuplet = self.tuplet
        for _ in range(dots):
            duration *= fractions.Fraction(3, 2)
        if tuplet == 3:
            duration *= fractions.Fraction(2, 3)
        elif tuplet == 5:
            duration *= fractions.Fraction(4, 5)
        return audioproc.MusicalDuration(duration)

    def property_changed(self, change: music.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()

    def set_pitch(self, pitch: value_types.Pitch) -> None:
        self.pitches[0] = pitch

    def add_pitch(self, pitch: value_types.Pitch) -> None:
        if pitch not in self.pitches:
            self.pitches.append(pitch)

    def remove_pitch(self, index: int) -> None:
        assert 0 <= index < len(self.pitches)
        del self.pitches[index]

    def set_accidental(self, index: int, accidental: str) -> None:
        assert 0 <= index < len(self.pitches)
        self.pitches[index] = self.pitches[index].add_accidental(accidental)

    def transpose(self, half_notes: int) -> None:
        for pidx, pitch in enumerate(self.pitches):
            self.pitches[pidx] = pitch.transposed(
                half_notes=half_notes % 12,
                octaves=half_notes // 12)


class ScoreMeasure(_model.ScoreMeasure):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()

        self.notes_changed.add(lambda _: self.content_changed.call())

    @property
    def track(self) -> 'ScoreTrack':
        return down_cast(ScoreTrack, super().track)

    @property
    def empty(self) -> bool:
        return len(self.notes) == 0

    def create_note(
            self,
            index: int,
            pitch: value_types.Pitch,
            duration: audioproc.MusicalDuration
    ) -> Note:
        assert 0 <= index <= len(self.notes)
        note = self._pool.create(
            Note,
            pitches=[pitch],
            base_duration=duration)
        self.notes.insert(index, note)
        return note

    def delete_note(self, note: Note) -> None:
        del self.notes[note.index]


class ScoreTrack(_model.ScoreTrack):
    measure_cls = ScoreMeasure

    def create(self, *, num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        for _ in range(num_measures):
            self.append_measure()

    def create_empty_measure(self, ref: Optional[base_track.Measure]) -> ScoreMeasure:
        measure = down_cast(ScoreMeasure, super().create_empty_measure(ref))

        if ref is not None:
            ref = down_cast(ScoreMeasure, ref)
            measure.key_signature = ref.key_signature
            measure.clef = ref.clef

        return measure

    def create_node_connector(
            self,
            message_cb: Callable[[audioproc.ProcessorMessage], None],
            audioproc_client: audioproc.AbstractAudioProcClient,
    ) -> ScoreTrackConnector:
        return ScoreTrackConnector(
            node=self, message_cb=message_cb, audioproc_client=audioproc_client)

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.ScoreTrackDescription

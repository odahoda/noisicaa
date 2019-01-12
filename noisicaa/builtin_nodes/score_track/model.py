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

from typing import cast, Any, Sequence
import fractions

from noisicaa import core
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import model
from noisicaa.builtin_nodes import model_registry_pb2
from . import node_description


class Note(model.ProjectChild):
    class NoteSpec(model.ObjectSpec):
        proto_type = 'note'
        proto_ext = model_registry_pb2.note

        pitches = model.WrappedProtoListProperty(model.Pitch)
        base_duration = model.WrappedProtoProperty(
            audioproc.MusicalDuration,
            default=audioproc.MusicalDuration(1, 4))
        dots = model.Property(int, default=0)
        tuplet = model.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.pitches_changed = core.Callback[model.PropertyListChange[model.Pitch]]()
        self.base_duration_changed = \
            core.Callback[model.PropertyChange[audioproc.MusicalDuration]]()
        self.dots_changed = core.Callback[model.PropertyChange[int]]()
        self.tuplet_changed = core.Callback[model.PropertyChange[int]]()

    @property
    def pitches(self) -> Sequence[model.Pitch]:
        return self.get_property_value('pitches')

    @property
    def base_duration(self) -> audioproc.MusicalDuration:
        return self.get_property_value('base_duration')

    @property
    def dots(self) -> int:
        return self.get_property_value('dots')

    @property
    def tuplet(self) -> int:
        return self.get_property_value('tuplet')

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

    def property_changed(self, change: model.PropertyChange) -> None:
        super().property_changed(change)
        if self.measure is not None:
            self.measure.content_changed.call()


class ScoreMeasure(model.Measure):
    class ScoreMeasureSpec(model.ObjectSpec):
        proto_type = 'score_measure'
        proto_ext = model_registry_pb2.score_measure

        clef = model.WrappedProtoProperty(model.Clef, default=model.Clef.Treble)
        key_signature = model.WrappedProtoProperty(
            model.KeySignature,
            default=model.KeySignature('C major'))
        notes = model.ObjectListProperty(Note)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.clef_changed = core.Callback[model.PropertyChange[model.Clef]]()
        self.key_signature_changed = \
            core.Callback[model.PropertyChange[model.KeySignature]]()
        self.notes_changed = core.Callback[model.PropertyListChange[Note]]()

        self.content_changed = core.Callback[None]()

    def setup(self) -> None:
        super().setup()

        self.notes_changed.add(lambda _: self.content_changed.call())


class ScoreTrack(model.MeasuredTrack):
    class ScoreTrackSpec(model.ObjectSpec):
        proto_type = 'score_track'
        proto_ext = model_registry_pb2.score_track

        transpose_octaves = model.Property(int, default=0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.transpose_octaves_changed = core.Callback[model.PropertyChange[int]]()

    @property
    def description(self) -> node_db.NodeDescription:
        return node_description.ScoreTrackDescription

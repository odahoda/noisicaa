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
from typing import Any, MutableSequence, Optional, Iterator, Iterable, Callable

from google.protobuf import message as protobuf

from noisicaa.core.typing_extra import down_cast
from noisicaa import audioproc
from noisicaa import model
from noisicaa.music import commands
from noisicaa.music import pmodel
from noisicaa.music import base_track
from noisicaa.builtin_nodes import commands_registry_pb2
from . import commands_pb2
from . import model as score_track_model

logger = logging.getLogger(__name__)


class ChangeNote(commands.Command):
    proto_type = 'change_note'
    proto_ext = commands_registry_pb2.change_note

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.ChangeNote, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx < len(measure.notes)
        note = measure.notes[pb.idx]

        if pb.HasField('pitch'):
            note.pitches[0] = model.Pitch(pb.pitch)

        if pb.HasField('duration'):
            note.base_duration = audioproc.MusicalDuration.from_proto(pb.duration)

        if pb.HasField('dots'):
            if pb.dots > note.max_allowed_dots:
                raise ValueError("Too many dots on note")
            note.dots = pb.dots

        if pb.HasField('tuplet'):
            if pb.tuplet not in (0, 3, 5):
                raise ValueError("Invalid tuplet type")
            note.tuplet = pb.tuplet

commands.Command.register_command(ChangeNote)


class InsertNote(commands.Command):
    proto_type = 'insert_note'
    proto_ext = commands_registry_pb2.insert_note

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.InsertNote, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx <= len(measure.notes)
        note = pool.create(
            Note,
            pitches=[model.Pitch(pb.pitch)],
            base_duration=audioproc.MusicalDuration.from_proto(pb.duration))
        measure.notes.insert(pb.idx, note)

commands.Command.register_command(InsertNote)


class DeleteNote(commands.Command):
    proto_type = 'delete_note'
    proto_ext = commands_registry_pb2.delete_note

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.DeleteNote, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx < len(measure.notes)
        del measure.notes[pb.idx]

commands.Command.register_command(DeleteNote)


class AddPitch(commands.Command):
    proto_type = 'add_pitch'
    proto_ext = commands_registry_pb2.add_pitch

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.AddPitch, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx < len(measure.notes)
        note = measure.notes[pb.idx]
        pitch = model.Pitch(pb.pitch)
        if pitch not in note.pitches:
            note.pitches.append(pitch)

commands.Command.register_command(AddPitch)


class RemovePitch(commands.Command):
    proto_type = 'remove_pitch'
    proto_ext = commands_registry_pb2.remove_pitch

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.RemovePitch, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx < len(measure.notes)
        note = measure.notes[pb.idx]
        assert 0 <= pb.pitch_idx < len(note.pitches)
        del note.pitches[pb.pitch_idx]

commands.Command.register_command(RemovePitch)


class SetClef(commands.Command):
    proto_type = 'set_clef'
    proto_ext = commands_registry_pb2.set_clef

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetClef, pb)
        track = down_cast(ScoreTrack, pool[self.proto.command.target])

        for measure_id in pb.measure_ids:
            measure = down_cast(ScoreMeasure, pool[measure_id])
            assert measure.is_child_of(track)
            measure.clef = model.Clef.from_proto(pb.clef)

commands.Command.register_command(SetClef)


class SetKeySignature(commands.Command):
    proto_type = 'set_key_signature'
    proto_ext = commands_registry_pb2.set_key_signature

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetKeySignature, pb)
        track = down_cast(ScoreTrack, pool[self.proto.command.target])

        for measure_id in pb.measure_ids:
            measure = down_cast(ScoreMeasure, pool[measure_id])
            assert measure.is_child_of(track)
            measure.key_signature = model.KeySignature.from_proto(pb.key_signature)

commands.Command.register_command(SetKeySignature)


class SetAccidental(commands.Command):
    proto_type = 'set_accidental'
    proto_ext = commands_registry_pb2.set_accidental

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.SetAccidental, pb)
        measure = down_cast(ScoreMeasure, pool[self.proto.command.target])

        assert 0 <= pb.idx < len(measure.notes)
        note = measure.notes[pb.idx]
        assert 0 <= pb.pitch_idx < len(note.pitches)

        note.pitches[pb.pitch_idx] = note.pitches[pb.pitch_idx].add_accidental(pb.accidental)

commands.Command.register_command(SetAccidental)


class TransposeNotes(commands.Command):
    proto_type = 'transpose_notes'
    proto_ext = commands_registry_pb2.transpose_notes

    def run(self, project: pmodel.Project, pool: pmodel.Pool, pb: protobuf.Message) -> None:
        pb = down_cast(commands_pb2.TransposeNotes, pb)
        track = down_cast(ScoreTrack, pool[self.proto.command.target])

        for note_id in pb.note_ids:
            note = down_cast(Note, pool[note_id])
            assert note.is_child_of(track)

            for pidx, pitch in enumerate(note.pitches):
                note.pitches[pidx] = pitch.transposed(
                    half_notes=pb.half_notes % 12,
                    octaves=pb.half_notes // 12)

commands.Command.register_command(TransposeNotes)


class Note(pmodel.ProjectChild, score_track_model.Note, pmodel.ObjectBase):
    def create(
            self, *,
            pitches: Optional[Iterable[model.Pitch]] = None,
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

    @property
    def pitches(self) -> MutableSequence[model.Pitch]:
        return self.get_property_value('pitches')

    @property
    def base_duration(self) -> audioproc.MusicalDuration:
        return self.get_property_value('base_duration')

    @base_duration.setter
    def base_duration(self, value: audioproc.MusicalDuration) -> None:
        self.set_property_value('base_duration', value)

    @property
    def dots(self) -> int:
        return self.get_property_value('dots')

    @dots.setter
    def dots(self, value: int) -> None:
        self.set_property_value('dots', value)

    @property
    def tuplet(self) -> int:
        return self.get_property_value('tuplet')

    @tuplet.setter
    def tuplet(self, value: int) -> None:
        self.set_property_value('tuplet', value)

    @property
    def measure(self) -> 'ScoreMeasure':
        return down_cast(ScoreMeasure, super().measure)


class ScoreMeasure(base_track.Measure, score_track_model.ScoreMeasure, pmodel.ObjectBase):
    @property
    def clef(self) -> model.Clef:
        return self.get_property_value('clef')

    @clef.setter
    def clef(self, value: model.Clef) -> None:
        self.set_property_value('clef', value)

    @property
    def key_signature(self) -> model.KeySignature:
        return self.get_property_value('key_signature')

    @key_signature.setter
    def key_signature(self, value: model.KeySignature) -> None:
        self.set_property_value('key_signature', value)

    @property
    def notes(self) -> MutableSequence[Note]:
        return self.get_property_value('notes')

    @property
    def track(self) -> 'ScoreTrack':
        return down_cast(ScoreTrack, super().track)

    @property
    def empty(self) -> bool:
        return len(self.notes) == 0


class ScoreTrackConnector(base_track.MeasuredTrackConnector):
    _node = None  # type: ScoreTrack

    def _add_track_listeners(self) -> None:
        self._listeners['transpose_octaves'] = self._node.transpose_octaves_changed.add(
            self.__transpose_octaves_changed)

    def _add_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        measure = down_cast(ScoreMeasure, mref.measure)
        self._listeners['measure:%s:notes' % mref.id] = measure.content_changed.add(
            lambda _=None: self.__measure_notes_changed(mref))  # type: ignore

    def _remove_measure_listeners(self, mref: pmodel.MeasureReference) -> None:
        self._listeners.pop('measure:%s:notes' % mref.id).remove()

    def _create_events(
            self, time: audioproc.MusicalTime, measure: pmodel.Measure
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

    def __transpose_octaves_changed(self, change: model.PropertyChange) -> None:
        self._update_measure_range(0, len(self._node.measure_list))

    def __measure_notes_changed(self, mref: pmodel.MeasureReference) -> None:
        self._update_measure_range(mref.index, mref.index + 1)


class ScoreTrack(base_track.MeasuredTrack, score_track_model.ScoreTrack, pmodel.ObjectBase):
    measure_cls = ScoreMeasure

    def create(self, *, num_measures: int = 1, **kwargs: Any) -> None:
        super().create(**kwargs)

        for _ in range(num_measures):
            self.append_measure()

    @property
    def transpose_octaves(self) -> int:
        return self.get_property_value('transpose_octaves')

    @transpose_octaves.setter
    def transpose_octaves(self, value: int) -> None:
        self.set_property_value('transpose_octaves', value)

    def create_empty_measure(self, ref: Optional[pmodel.Measure]) -> ScoreMeasure:
        measure = down_cast(ScoreMeasure, super().create_empty_measure(ref))

        if ref is not None:
            ref = down_cast(ScoreMeasure, ref)
            measure.key_signature = ref.key_signature
            measure.clef = ref.clef

        return measure

    def create_node_connector(
            self, message_cb: Callable[[audioproc.ProcessorMessage], None]
    ) -> ScoreTrackConnector:
        return ScoreTrackConnector(node=self, message_cb=message_cb)

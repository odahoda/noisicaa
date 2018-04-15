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

# TODO: pylint-unclean
# mypy: loose

import functools
import logging
from typing import cast

from noisicaa import core
from noisicaa import audioproc

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from . import base_track
from . import model
from . import state
from . import commands
from . import pipeline_graph
from . import misc
from . import project

logger = logging.getLogger(__name__)


class SetInstrument(commands.Command):
    instrument = core.Property(str)

    def __init__(self, instrument=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument = instrument

    def run(self, track):
        assert isinstance(track, ScoreTrack)

        track.instrument = self.instrument

        for mutation in track.instrument_node.get_update_mutations():
            cast(project.BaseProject, track.project).handle_pipeline_mutation(mutation)

commands.Command.register_command(SetInstrument)


class ChangeNote(commands.Command):
    idx = core.Property(int)
    pitch = core.Property(str, allow_none=True)
    duration = core.Property(audioproc.MusicalDuration, allow_none=True)
    dots = core.Property(int, allow_none=True)
    tuplet = core.Property(int, allow_none=True)

    def __init__(self, idx=None, pitch=None, duration=None, dots=None, tuplet=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx
            self.pitch = pitch
            self.duration = duration
            self.dots = dots
            self.tuplet = tuplet

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]

        if self.pitch is not None:
            note.pitches[0] = Pitch(self.pitch)

        if self.duration is not None:
            note.base_duration = self.duration

        if self.dots is not None:
            if self.dots > note.max_allowed_dots:
                raise ValueError("Too many dots on note")
            note.dots = self.dots

        if self.tuplet is not None:
            if self.tuplet not in (0, 3, 5):
                raise ValueError("Invalid tuplet type")
            note.tuplet = self.tuplet

commands.Command.register_command(ChangeNote)


class InsertNote(commands.Command):
    idx = core.Property(int)
    pitch = core.Property(str)
    duration = core.Property(audioproc.MusicalDuration)

    def __init__(self, idx=None, pitch=None, duration=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx
            self.pitch = pitch
            self.duration = duration

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx <= len(measure.notes)
        note = Note(pitches=[Pitch(self.pitch)], base_duration=self.duration)
        measure.notes.insert(self.idx, note)

commands.Command.register_command(InsertNote)


class DeleteNote(commands.Command):
    idx = core.Property(int)

    def __init__(self, idx=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        del measure.notes[self.idx]

commands.Command.register_command(DeleteNote)


class AddPitch(commands.Command):
    idx = core.Property(int)
    pitch = core.Property(str)

    def __init__(self, idx=None, pitch=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx
            self.pitch = pitch

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        pitch = Pitch(self.pitch)
        if pitch not in note.pitches:
            note.pitches.append(pitch)

commands.Command.register_command(AddPitch)


class RemovePitch(commands.Command):
    idx = core.Property(int)
    pitch_idx = core.Property(int)

    def __init__(self, idx=None, pitch_idx=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx
            self.pitch_idx = pitch_idx

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        assert 0 <= self.pitch_idx < len(note.pitches)
        del note.pitches[self.pitch_idx]

commands.Command.register_command(RemovePitch)


class SetClef(commands.Command):
    measure_ids = core.ListProperty(str)
    clef = core.Property(str)

    def __init__(self, measure_ids=None, clef=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.measure_ids.extend(measure_ids)
            self.clef = clef

    def run(self, track):
        assert isinstance(track, ScoreTrack)

        for measure_id in self.measure_ids:
            measure = cast(ScoreMeasure, track.project.get_object(measure_id))
            assert measure.is_child_of(track)
            measure.clef = Clef(self.clef)

commands.Command.register_command(SetClef)


class SetKeySignature(commands.Command):
    measure_ids = core.ListProperty(str)
    key_signature = core.Property(str)

    def __init__(self, measure_ids=None, key_signature=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.measure_ids.extend(measure_ids)
            self.key_signature = key_signature

    def run(self, track):
        assert isinstance(track, ScoreTrack)

        for measure_id in self.measure_ids:
            measure = cast(ScoreMeasure, track.project.get_object(measure_id))
            assert measure.is_child_of(track)
            measure.key_signature = KeySignature(self.key_signature)

commands.Command.register_command(SetKeySignature)


class SetAccidental(commands.Command):
    idx = core.Property(int)
    pitch_idx = core.Property(int)
    accidental = core.Property(str)

    def __init__(self, idx=None, pitch_idx=None, accidental=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.idx = idx
            self.pitch_idx = pitch_idx
            self.accidental = accidental

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        assert 0 <= self.pitch_idx < len(note.pitches)

        note.pitches[self.pitch_idx] = note.pitches[self.pitch_idx].add_accidental(self.accidental)

commands.Command.register_command(SetAccidental)


class TransposeNotes(commands.Command):
    note_ids = core.ListProperty(str)
    half_notes = core.Property(int)

    def __init__(self, note_ids=None, half_notes=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.note_ids.extend(note_ids)
            self.half_notes = half_notes

    def run(self, track):
        assert isinstance(track, ScoreTrack)

        root = track.root

        for note_id in self.note_ids:
            note = cast(Note, root.get_object(note_id))
            assert note.is_child_of(track)

            for pidx, pitch in enumerate(note.pitches):
                note.pitches[pidx] = pitch.transposed(
                    half_notes=self.half_notes % 12,
                    octaves=self.half_notes // 12)

commands.Command.register_command(TransposeNotes)


class Note(model.Note, state.StateBase):
    def __init__(self,
                 pitches=None, base_duration=None, dots=0, tuplet=0,
                 state=None):
        super().__init__(state=state)
        if state is None:
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

    def __str__(self):
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

    def property_changed(self, changes):
        super().property_changed(changes)
        if self.measure is not None:
            self.measure.listeners.call('notes-changed')

state.StateBase.register_class(Note)


class ScoreMeasure(model.ScoreMeasure, base_track.Measure):
    def __init__(self, state=None):
        super().__init__(state=state)
        if state is None:
            pass
        self.listeners.add(
            'notes', lambda *args: self.listeners.call('notes-changed'))

    @property
    def empty(self):
        return len(self.notes) == 0

state.StateBase.register_class(ScoreMeasure)


class ScoreTrackConnector(base_track.MeasuredTrackConnector):
    def _add_track_listeners(self):
        self._listeners['transpose_octaves'] = self._track.listeners.add(
            'transpose_octaves', self.__transpose_octaves_changed)

    def _add_measure_listeners(self, mref):
        self._listeners['measure:%s:notes' % mref.id] = mref.measure.listeners.add(
            'notes-changed', functools.partial(
                self.__measure_notes_changed, mref))

    def _remove_measure_listeners(self, mref):
        self._listeners.pop('measure:%s:notes' % mref.id).remove()

    def _create_events(self, time, measure):
        for note in measure.notes:
            if not note.is_rest:
                for pitch in note.pitches:
                    pitch = pitch.transposed(octaves=self._track.transpose_octaves)
                    event = base_track.PianoRollInterval(
                        time, time + note.duration, pitch, 127)
                    yield event

            time += note.duration

    def __transpose_octaves_changed(self, change):
        self._update_measure_range(0, len(self._track.measure_list))

    def __measure_notes_changed(self, mref):
        self._update_measure_range(mref.index, mref.index + 1)


class ScoreTrack(model.ScoreTrack, base_track.MeasuredTrack):
    measure_cls = ScoreMeasure

    def __init__(
            self, instrument=None, num_measures=1, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            if instrument is None:
                self.instrument = 'sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2?bank=0&preset=0'
            else:
                self.instrument = instrument

            for _ in range(num_measures):
                self.append_measure()

    def create_empty_measure(self, ref):
        measure = super().create_empty_measure(ref)

        if ref is not None:
            measure.key_signature = ref.key_signature
            measure.clef = ref.clef

        return measure

    def create_track_connector(self, **kwargs):
        return ScoreTrackConnector(
            track=self,
            node_id=self.event_source_name,
            **kwargs)

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    @property
    def event_source_node(self):
        if self.event_source_id is None:
            raise ValueError("No event source node found.")
        return self.root.get_object(self.event_source_id)

    @property
    def instr_name(self):
        return '%s-instr' % self.id

    @property
    def instrument_node(self):
        if self.instrument_id is None:
            raise ValueError("No instrument node found.")

        return self.root.get_object(self.instrument_id)

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        instrument_node = pipeline_graph.InstrumentPipelineGraphNode(
            name="Track Instrument",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(instrument_node)
        self.instrument_id = instrument_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                instrument_node, 'out:left', self.mixer_node, 'in:left'))
        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                instrument_node, 'out:right', self.mixer_node, 'in:right'))

        event_source_node = pipeline_graph.PianoRollPipelineGraphNode(
            name="Track Events",
            graph_pos=instrument_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.project.add_pipeline_graph_node(event_source_node)
        self.event_source_id = event_source_node.id

        self.project.add_pipeline_graph_connection(
            pipeline_graph.PipelineGraphConnection(
                event_source_node, 'out', instrument_node, 'in'))

    def remove_pipeline_nodes(self):
        self.project.remove_pipeline_graph_node(self.event_source_node)
        self.event_source_id = None
        self.project.remove_pipeline_graph_node(self.instrument_node)
        self.instrument_id = None
        super().remove_pipeline_nodes()

state.StateBase.register_class(ScoreTrack)

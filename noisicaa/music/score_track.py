#!/usr/bin/python3

import functools
import logging

from noisicaa import core

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .track import MeasureReference, MeasuredTrack, Measure, EntitySource, MeasuredEventSetConnector, EventSetEntitySource
from .time import Duration
from . import model
from . import state
from . import commands
from . import mutations
from . import pipeline_graph
from . import misc
from . import time
from . import event_set
from . import time_mapper

logger = logging.getLogger(__name__)


class SetInstrument(commands.Command):
    instrument = core.Property(str)

    def __init__(self, instrument=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument = instrument

    def run(self, track):
        assert isinstance(track, MeasuredTrack)

        track.instrument = self.instrument
        track.instrument_node.update_pipeline()

commands.Command.register_command(SetInstrument)


class ChangeNote(commands.Command):
    idx = core.Property(int)
    pitch = core.Property(str, allow_none=True)
    duration = core.Property(Duration, allow_none=True)
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
    duration = core.Property(Duration)

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
    clef = core.Property(str)

    def __init__(self, clef=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.clef = clef

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        measure.clef = Clef(self.clef)

commands.Command.register_command(SetClef)


class SetKeySignature(commands.Command):
    key_signature = core.Property(str)

    def __init__(self, key_signature=None, state=None):
        super().__init__(state=state)
        if state is None:
            self.key_signature = key_signature

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

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
            note = root.get_object(note_id)
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
                base_duration = Duration(1, 4)
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


class ScoreMeasure(model.ScoreMeasure, Measure):
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


class ScoreEntitySource(EventSetEntitySource):
    def _create_connector(self, track, event_set):
        return EventSetConnector(track, event_set)


class EventSetConnector(MeasuredEventSetConnector):
    def __init__(self, track, event_set):
        super().__init__(track, event_set)

    def _add_track_listeners(self):
        self._listeners['transpose_octaves'] = self._track.listeners.add(
            'transpose_octaves', self.__transpose_octaves_changed)

    def _add_measure_listeners(self, mref):
        self._listeners['measure:%s:notes' % mref.id] = mref.measure.listeners.add(
            'notes-changed', functools.partial(
                self.__measure_notes_changed, mref))

    def _remove_measure_listeners(self, mref):
        self._listeners.pop('measure:%s:notes' % mref.id).remove()

    def _create_events(self, timepos, measure):
        for note in measure.notes:
            if not note.is_rest:
                for pitch in note.pitches:
                    pitch = pitch.transposed(octaves=self._track.transpose_octaves)
                    event = event_set.NoteEvent(timepos, timepos + note.duration, pitch, 127)
                    yield event

            timepos += note.duration

    def __transpose_octaves_changed(self, change):
        timepos = time.Duration()
        for mref in self._track.measure_list:
            self._update_measure(timepos, mref)
            timepos += mref.measure.duration

    def __measure_notes_changed(self, mref):
        timepos = time.Duration()
        for mr in self._track.measure_list:
            if mr.index == mref.index:
                assert mr is mref
                self._update_measure(timepos, mref)
                break

            timepos += mref.measure.duration


class ScoreTrack(model.ScoreTrack, MeasuredTrack):
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

    def create_entity_source(self):
        return ScoreEntitySource(self)

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
        self.sheet.add_pipeline_graph_node(instrument_node)
        self.instrument_id = instrument_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            instrument_node, 'out', self.mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

        event_source_node = pipeline_graph.EventSourcePipelineGraphNode(
            name="Track Events",
            graph_pos=instrument_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(event_source_node)
        self.event_source_id = event_source_node.id

        conn = pipeline_graph.PipelineGraphConnection(
            event_source_node, 'out', instrument_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.event_source_node)
        self.event_source_id = None
        self.sheet.remove_pipeline_graph_node(self.instrument_node)
        self.instrument_id = None
        super().remove_pipeline_nodes()

state.StateBase.register_class(ScoreTrack)

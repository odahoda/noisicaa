#!/usr/bin/python3

import logging

from noisicaa import core
from noisicaa.audioproc.events import NoteOnEvent, NoteOffEvent

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .track import Track, Measure, EventSource
from .time import Duration
from . import model
from . import state
from . import commands
from . import instruments
from . import mutations
from . import pipeline_graph
from . import misc

logger = logging.getLogger(__name__)


class SetInstrument(commands.Command):
    instrument_type = core.Property(str)
    instrument_args = core.DictProperty()

    def __init__(self, instrument_type=None, instrument_args=None,
                 state=None):
        super().__init__(state=state)
        if state is None:
            self.instrument_type = instrument_type
            self.instrument_args.update(instrument_args)

    def run(self, track):
        assert isinstance(track, Track)

        assert self.instrument_type == 'SoundFontInstrument'
        instr = instruments.SoundFontInstrument(**self.instrument_args)

        track.instrument = instr
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

state.StateBase.register_class(Note)


class ScoreMeasure(model.ScoreMeasure, Measure):
    def __init__(self, state=None):
        super().__init__(state=state)
        if state is None:
            pass

    @property
    def empty(self):
        return len(self.notes) == 0

state.StateBase.register_class(ScoreMeasure)


class ScoreEventSource(EventSource):
    def __init__(self, track):
        super().__init__(track)
        self._active_pitches = []
        self._current_measure = 0
        self._current_tick = 0
        self._current_micro_sample_pos = 0

    def get_events(self, start_sample_pos, end_sample_pos):
        # logger.debug("get_events(%d, %d)", start_sample_pos, end_sample_pos)

        while self._current_micro_sample_pos < 1000000 * end_sample_pos:
            measure = self._track.measure_list[self._current_measure].measure
            sample_pos = self._current_micro_sample_pos // 1000000

            if self._current_micro_sample_pos >= 1000000 * start_sample_pos:
                t = 0
                for idx, note in enumerate(measure.notes):
                    if t == self._current_tick:
                        for pitch in self._active_pitches:
                            yield NoteOffEvent(sample_pos, pitch)
                        self._active_pitches.clear()

                        if not note.is_rest:
                            for pitch in note.pitches:
                                pitch = pitch.transposed(
                                    octaves=self._track.transpose_octaves)
                                # logger.debug(
                                #     "Play %s @%d for %s",
                                #     pitch.name, sample_pos, note.duration)
                                yield NoteOnEvent(
                                    sample_pos, pitch,
                                    tags={(measure.id, 'noteon', idx)})
                                self._active_pitches.append(pitch)
                    t += note.duration.ticks

            # This should be a function of (measure, tick)
            bpm = self._track.sheet.get_bpm(
                self._current_measure, self._current_tick)
            micro_samples_per_tick = int(
                1000000 * 4 * 44100 * 60 // bpm * Duration.tick_duration)

            self._current_micro_sample_pos += micro_samples_per_tick
            self._current_tick += 1
            if self._current_tick >= measure.duration.ticks:
                self._current_tick = 0
                self._current_measure += 1
                if self._current_measure >= len(self._track.measure_list):
                    self._current_measure = 0


class ScoreTrack(model.ScoreTrack, Track):
    measure_cls = ScoreMeasure

    def __init__(
            self, instrument=None, num_measures=1, state=None, **kwargs):
        super().__init__(state=state, **kwargs)

        if state is None:
            if instrument is None:
                self.instrument = instruments.SoundFontInstrument(
                    name="Default Piano",
                    path='/usr/share/sounds/sf2/FluidR3_GM.sf2',
                    bank=0,
                    preset=0)
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

    def create_event_source(self):
        return ScoreEventSource(self)

    @property
    def event_source_name(self):
        return '%s-events' % self.id

    @property
    def event_source_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.EventSourcePipelineGraphNode) and node.track is self:
                return node

        raise ValueError("No event source node found.")

    @property
    def instr_name(self):
        return '%s-instr' % self.id

    @property
    def instrument_node(self):
        for node in self.sheet.pipeline_graph_nodes:
            if isinstance(node, pipeline_graph.InstrumentPipelineGraphNode) and node.track is self:
                return node

        raise ValueError("No instrument node found.")

    def add_pipeline_nodes(self):
        super().add_pipeline_nodes()

        mixer_node = self.mixer_node

        instrument_node = pipeline_graph.InstrumentPipelineGraphNode(
            name="Track Instrument",
            graph_pos=mixer_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(instrument_node)

        conn = pipeline_graph.PipelineGraphConnection(
            instrument_node, 'out', self.mixer_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

        event_source_node = pipeline_graph.EventSourcePipelineGraphNode(
            name="Track Events",
            graph_pos=instrument_node.graph_pos - misc.Pos2F(200, 0),
            track=self)
        self.sheet.add_pipeline_graph_node(event_source_node)

        conn = pipeline_graph.PipelineGraphConnection(
            event_source_node, 'out', instrument_node, 'in')
        self.sheet.add_pipeline_graph_connection(conn)

    def remove_pipeline_nodes(self):
        self.sheet.remove_pipeline_graph_node(self.event_source_node)
        self.sheet.remove_pipeline_graph_node(self.instrument_node)
        super().remove_pipeline_nodes()

state.StateBase.register_class(ScoreTrack)

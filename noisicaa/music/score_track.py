#!/usr/bin/python3

import logging
import fractions

from noisicaa import core

from noisicaa.audioproc.events import NoteOnEvent, NoteOffEvent

from .pitch import Pitch
from .clef import Clef
from .key_signature import KeySignature
from .track import Track, Measure, EventSource
from .time import Duration

logger = logging.getLogger(__name__)


class ChangeNote(core.Command):
    def __init__(self, idx, pitch=None, duration=None, dots=None, tuplet=None):
        super().__init__()
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


class InsertNote(core.Command):
    def __init__(self, idx, pitch, duration):
        super().__init__()
        self.idx = idx
        self.pitch = pitch
        self.duration = duration

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx <= len(measure.notes)
        note = Note(pitches=[Pitch(self.pitch)], base_duration=self.duration)
        measure.notes.insert(self.idx, note)


class DeleteNote(core.Command):
    def __init__(self, idx):
        super().__init__()
        self.idx = idx

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        del measure.notes[self.idx]


class AddPitch(core.Command):
    def __init__(self, idx, pitch):
        super().__init__()
        self.idx = idx
        self.pitch = pitch

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        pitch = Pitch(self.pitch)
        if pitch not in note.pitches:
            note.pitches.append(pitch)


class RemovePitch(core.Command):
    def __init__(self, idx, pitch_idx):
        super().__init__()
        self.idx = idx
        self.pitch_idx = pitch_idx

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        assert 0 <= self.pitch_idx < len(note.pitches)
        del note.pitches[self.pitch_idx]


class SetClef(core.Command):
    def __init__(self, clef):
        super().__init__()
        self.clef = clef

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        measure.clef = Clef(self.clef)


class SetKeySignature(core.Command):
    def __init__(self, key_signature):
        super().__init__()
        self.key_signature = key_signature

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        measure.key_signature = KeySignature(self.key_signature)

class SetAccidental(core.Command):
    def __init__(self, idx, pitch_idx, accidental):
        super().__init__()
        self.idx = idx
        self.pitch_idx = pitch_idx
        self.accidental = accidental

    def run(self, measure):
        assert isinstance(measure, ScoreMeasure)

        assert 0 <= self.idx < len(measure.notes)
        note = measure.notes[self.idx]
        assert 0 <= self.pitch_idx < len(note.pitches)
        note.pitches[self.pitch_idx].accidental = self.accidental


class Note(core.StateBase, core.CommandTarget):
    pitches = core.ListProperty(Pitch)
    base_duration = core.Property(Duration)
    dots = core.Property(int, default=0)
    tuplet = core.Property(int, default=0)

    def __init__(self,
                 pitches=None, base_duration=None, dots=0, tuplet=0,
                 state=None):
        super().__init__()
        self.init_state(state)
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

    @property
    def is_rest(self):
        return len(self.pitches) == 1 and self.pitches[0].is_rest

    @property
    def max_allowed_dots(self):
        if self.base_duration <= Duration(1, 32):
            return 0
        if self.base_duration <= Duration(1, 16):
            return 1
        if self.base_duration <= Duration(1, 8):
            return 2
        return 3

    @property
    def duration(self):
        duration = self.base_duration
        for _ in range(self.dots):
            duration *= fractions.Fraction(3, 2)
        if self.tuplet == 3:
            duration *= fractions.Fraction(2, 3)
        elif self.tuplet == 5:
            duration *= fractions.Fraction(4, 5)
        return Duration(duration)

class ScoreMeasure(Measure):
    clef = core.Property(Clef, default=Clef.Treble)
    key_signature = core.Property(KeySignature, default=KeySignature('C major'))
    notes = core.ObjectListProperty(cls=Note)

    def __init__(self, state=None):
        super().__init__(state)
        if state is None:
            pass

    @property
    def time_signature(self):
        return self.sheet.get_time_signature(self.index)

    @property
    def empty(self):
        return len(self.notes) == 0

Measure.register_subclass(ScoreMeasure)


class ScoreEventSource(EventSource):
    def __init__(self, track):
        super().__init__(track)
        self._active_pitches = []
        self._current_measure = 0
        self._current_tick = 0
        self._current_micro_timepos = 0

    def get_events(self, start_timepos, end_timepos):
        logger.debug("get_events(%d, %d)", start_timepos, end_timepos)

        while self._current_micro_timepos < 1000000 * end_timepos:
            measure = self._track.measures[self._current_measure]

            if self._current_micro_timepos >= 1000000 * start_timepos:
                timepos = self._current_micro_timepos // 1000000

                t = 0
                for idx, note in enumerate(measure.notes):
                    if t == self._current_tick:
                        for pitch in self._active_pitches:
                            yield NoteOffEvent(timepos, pitch)
                        self._active_pitches.clear()

                        if not note.is_rest:
                            for pitch in note.pitches:
                                pitch = pitch.transposed(
                                    octaves=self._track.transpose_octaves)
                                logger.debug(
                                    "Play %s @%d for %s",
                                    pitch.name, timepos, note.duration)
                                yield NoteOnEvent(
                                    timepos, pitch,
                                    tags={(measure.address, 'noteon', idx)})
                                self._active_pitches.append(pitch)
                    t += note.duration.ticks

            # This should be a function of (measure, tick)
            bpm = self._track.sheet.get_bpm(
                self._current_measure, self._current_tick)
            micro_samples_per_tick = int(
                1000000 * 4 * 44100 * 60 // bpm * Duration.tick_duration)

            self._current_micro_timepos += micro_samples_per_tick
            self._current_tick += 1
            if self._current_tick >= measure.duration.ticks:
                self._current_tick = 0
                self._current_measure += 1
                if self._current_measure >= len(self._track.measures):
                    self._current_measure = 0


class ScoreTrack(Track):
    measure_cls = ScoreMeasure
    transpose_octaves = core.Property(int, default=0)

    def __init__(self, name=None, num_measures=1, state=None):
        super().__init__(name, state)

        if state is None:
            for _ in range(num_measures):
                self.measures.append(ScoreMeasure())
            self.update_measures()

    def create_empty_measure(self, ref):
        measure = super().create_empty_measure(ref)

        if ref is not None:
            measure.key_signature = ref.key_signature
            measure.clef = ref.clef

        return measure

    def create_event_source(self):
        return ScoreEventSource(self)

Track.register_subclass(ScoreTrack)

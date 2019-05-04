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

import re
from typing import Optional, Union, Dict, List, Set, Tuple

from google.protobuf import message as protobuf

from . import proto_value
from . import value_types_pb2
from . import key_signature as key_signature_lib

NOTE_TO_MIDI = {}  # type: Dict[str, int]
MIDI_TO_NOTE = {}  # type: Dict[int, str]

def _fill_midi_maps(note_to_midi: Dict[str, int], midi_to_note: Dict[int, str]) -> None:
    note_names = [
        ('C',),
        ('C#', 'Db'),
        ('D',),
        ('D#', 'Eb'),
        ('E',),
        ('F',),
        ('F#', 'Gb'),
        ('G',),
        ('G#', 'Ab'),
        ('A',),
        ('A#', 'Bb'),
        ('B',)
    ]  # type: List[Tuple[str, ...]]

    k = 0
    for o in range(10):
        for n in note_names:
            if k < 128:
                for p in n:
                    note_to_midi['%s%d' % (p, o)] = k
                midi_to_note[k] = '%s%d' % (n[0], o)
            k += 1

_fill_midi_maps(NOTE_TO_MIDI, MIDI_TO_NOTE)


class Pitch(proto_value.ProtoValue):
    _values = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G',
               'G#', 'Ab', 'A', 'A#', 'Bb', 'B']

    def __init__(self, name: Optional[Union['Pitch', str]] = None) -> None:
        if isinstance(name, Pitch):
            self._is_rest = name._is_rest  # type: bool
            self._value = name._value  # type: str
            self._accidental = name._accidental  # type: str
            self._octave = name._octave  # type: int
        elif name == 'r':
            self._is_rest = True
            self._value = None
            self._accidental = None
            self._octave = None
        else:
            self._is_rest = False

            m = re.match(r'([CDEFGAB])([b#]?)(-?\d)$', name)
            if m is None:
                raise ValueError('Bad pitch name %r' % name)

            value = m.group(1)
            if value not in self._values:
                raise ValueError('Bad value %s' % value)
            self._value = value

            self._accidental = m.group(2)

            octave = int(m.group(3))
            if octave < -1 or octave > 7:
                raise ValueError('Bad octave %s' % octave)
            self._octave = octave

    def to_proto(self) -> value_types_pb2.Pitch:
        return value_types_pb2.Pitch(name=self.name)

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'Pitch':
        if not isinstance(pb, value_types_pb2.Pitch):
            raise TypeError(type(pb).__name__)
        return Pitch(pb.name)

    @classmethod
    def from_midi(cls, midi: int) -> 'Pitch':
        return cls(MIDI_TO_NOTE[midi])

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return 'Pitch(%s)' % self.name

    def __hash__(self) -> int:
        return hash((self._is_rest, self._value, self._accidental, self._octave))

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False

        if not isinstance(other, Pitch):
            raise TypeError(
                "Can't compare %s to %s" % (type(self).__name__, type(other).__name__))

        return (self._is_rest, self._octave, self._value, self._accidental) == (
            self._is_rest, other._octave, other._value, other._accidental)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Pitch):
            raise TypeError(
                "Can't compare %s to %s" % (type(self).__name__, type(other).__name__))

        return (self._is_rest, self._octave, 'CDEFGAB'.index(self._value), self._accidental) > (
            self._is_rest, other._octave, 'CDEFGAB'.index(other._value), other._accidental)

    @property
    def name(self) -> str:
        if self._is_rest:
            return 'r'
        else:
            return '%s%s%d' % (self._value, self._accidental, self._octave)

    @property
    def is_rest(self) -> bool:
        return self._is_rest

    @property
    def value(self) -> str:
        assert not self._is_rest
        return self._value

    @property
    def accidental(self) -> str:
        assert not self._is_rest
        return self._accidental

    def add_accidental(self, accidental: str) -> 'Pitch':
        assert not self._is_rest
        assert accidental in ('', '#', 'b', '##', 'bb')
        assert accidental in self.valid_accidentals
        p = self.__class__(self)
        p._accidental = accidental
        return p

    _valid_accidental_map = {
        'C': {'', '#'},
        'D': {'', 'b', '#'},
        'E': {'', 'b'},
        'F': {'', '#'},
        'G': {'', 'b', '#'},
        'A': {'', 'b', '#'},
        'B': {'', 'b'},
    }

    @property
    def valid_accidentals(self) -> Set[str]:
        if self._is_rest:
            return set()
        return self._valid_accidental_map[self.value]

    @property
    def octave(self) -> int:
        assert not self._is_rest
        return self._octave

    @property
    def stave_line(self) -> int:
        assert not self._is_rest
        return 'CDEFGAB'.index(self._value) + 7 * self._octave

    @classmethod
    def name_from_stave_line(
            cls, line: int, key_signature: Optional[key_signature_lib.KeySignature] = None) -> str:
        octave = line // 7
        value = 'CDEFGAB'[line % 7]
        if key_signature is not None:
            accidental = key_signature.accidental_map[value]
        else:
            accidental = ''
        return '%s%s%d' % (value, accidental, octave)

    @property
    def midi_note(self) -> int:
        try:
            return NOTE_TO_MIDI[self.name]
        except KeyError:
            return 23  # Ehh...

    _transpose_up = {
        # pylint: disable=bad-whitespace
        'C':  ('C#', 0),
        'C#': ('D',  0),
        'Db': ('D',  0),
        'D':  ('D#', 0),
        'D#': ('E',  0),
        'Eb': ('E',  0),
        'E':  ('F',  0),
        'F':  ('F#', 0),
        'F#': ('G',  0),
        'Gb': ('G',  0),
        'G':  ('G#', 0),
        'G#': ('A',  0),
        'Ab': ('A',  0),
        'A':  ('A#', 0),
        'A#': ('B',  0),
        'Bb': ('B',  0),
        'B':  ('C',  1),
    }

    _transpose_down = {
        # pylint: disable=bad-whitespace
        'C':  ('B', -1),
        'C#': ('C',  0),
        'Db': ('C',  0),
        'D':  ('Db', 0),
        'D#': ('D',  0),
        'Eb': ('D',  0),
        'E':  ('Eb', 0),
        'F':  ('E',  0),
        'F#': ('F',  0),
        'Gb': ('F',  0),
        'G':  ('Gb', 0),
        'G#': ('G',  0),
        'Ab': ('G',  0),
        'A':  ('Ab', 0),
        'A#': ('A',  0),
        'Bb': ('A',  0),
        'B':  ('Bb', 0),
    }

    def transposed(self, half_notes: int = 0, octaves: int = 0) -> 'Pitch':
        ttab = self._transpose_down if half_notes < 0 else self._transpose_up
        note = '%s%s' % (self._value, self._accidental)
        octave = self._octave + octaves
        for _ in range(abs(half_notes)):
            note, o = ttab[note]
            octave += o

        return Pitch('%s%d' % (note, max(-1, min(7, octave))))

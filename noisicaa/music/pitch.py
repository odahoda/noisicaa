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

import re

NOTE_TO_MIDI = {}
MIDI_TO_NOTE = {}

k = 0
for o in range(10):
    for n in [('C',),
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
              ('B',)]:
        if k < 128:
            for p in n:
                NOTE_TO_MIDI['%s%d' % (p, o)] = k
            MIDI_TO_NOTE[k] = '%s%d' % (n[0], o)
        k += 1


class Pitch(object):
    _values = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G',
               'G#', 'Ab', 'A', 'A#', 'Bb', 'B']

    def __init__(self, name=None):
        if isinstance(name, Pitch):
            self._is_rest = name._is_rest
            self._value = name._value
            self._accidental = name._accidental
            self._octave = name._octave
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

    @classmethod
    def from_midi(cls, midi):
        return cls(MIDI_TO_NOTE[midi])

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Pitch(%s)' % self.name

    def __hash__(self):
        return hash((self._is_rest, self._value, self._accidental, self._octave))

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, Pitch):
            raise TypeError(
                "Can't compare %s to %s" % (
                    type(self).__name__, type(other).__name__))

        # pylint: disable=protected-access
        return (self._is_rest, self._octave, self._value, self._accidental) == (
            self._is_rest, other._octave, other._value, other._accidental)

    def __gt__(self, other):
        if not isinstance(other, Pitch):
            raise TypeError(
                "Can't compare %s to %s" % (
                    type(self).__name__, type(other).__name__))

        # pylint: disable=protected-access
        return (self._is_rest, self._octave, 'CDEFGAB'.index(self._value), self._accidental) > (
            self._is_rest, other._octave, 'CDEFGAB'.index(other._value), other._accidental)

    @property
    def name(self):
        if self._is_rest:
            return 'r'
        else:
            return '%s%s%d' % (self._value, self._accidental, self._octave)

    @property
    def is_rest(self):
        return self._is_rest

    @property
    def value(self):
        assert not self._is_rest
        return self._value

    @property
    def accidental(self):
        assert not self._is_rest
        return self._accidental

    def add_accidental(self, accidental):
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
    def valid_accidentals(self):
        if self._is_rest:
            return set()
        return self._valid_accidental_map[self.value]

    @property
    def octave(self):
        assert not self._is_rest
        return self._octave

    @property
    def stave_line(self):
        assert not self._is_rest
        return 'CDEFGAB'.index(self._value) + 7 * self._octave

    @classmethod
    def name_from_stave_line(cls, line, key_signature=None):
        octave = line // 7
        value = 'CDEFGAB'[line % 7]
        if key_signature is not None:
            accidental = key_signature.accidental_map[value]
        else:
            accidental = ''
        return '%s%s%d' % (value, accidental, octave)

    @property
    def midi_note(self):
        try:
            return NOTE_TO_MIDI[self.name]
        except KeyError:
            return 23  # Ehh...

    _transpose_up = {
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

    def transposed(self, half_notes=0, octaves=0):
        ttab = self._transpose_down if half_notes < 0 else self._transpose_up
        note = '%s%s' % (self._value, self._accidental)
        octave = self._octave + octaves
        for _ in range(abs(half_notes)):
            note, o = ttab[note]
            octave += o

        return Pitch('%s%d' % (note, max(-1, min(7, octave))))

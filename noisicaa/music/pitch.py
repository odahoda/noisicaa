#!/usr/bin/python3

import re

NOTE_TO_MIDI = {}

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
        k += 1


class Pitch(object):
    _values = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G',
               'G#', 'Ab', 'A', 'A#', 'Bb', 'B']

    def __init__(self, name=None):
        if name == 'r':
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

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Pitch(%s)' % self.name

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

    @accidental.setter
    def accidental(self, accidental):
        assert not self._is_rest
        assert accidental in ('', '#', 'b', '##', 'bb')
        assert accidental in self.valid_accidentals
        self._accidental = accidental

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

    def transposed(self, octaves=0):
        return Pitch('%s%s%d' % (
            self._value,
            self._accidental,
            max(-1, min(7, self._octave + octaves))))

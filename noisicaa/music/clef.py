#!/usr/bin/python3

import enum

from .pitch import Pitch


@enum.unique
class Clef(enum.Enum):
    FrenchViolin = 'french-violin'
    Treble = 'treble'
    Soprano = 'soprano'
    MezzoSoprano = 'mezzo-soprano'
    Alto = 'alto'
    Tenor = 'tenor'
    Baritone = 'baritone'
    Bass = 'bass'
    Subbass = 'subbass'

    @property
    def symbol(self):
        return _clef_data[self][0]

    @property
    def base_pitch(self):
        return _clef_data[self][1]

    @property
    def center_pitch(self):
        return _clef_data[self][2]

    @property
    def base_octave(self):
        return _clef_data[self][3]


# (symbol, base_pitch, center_pitch, base_octave)
_clef_data = {
    Clef.FrenchViolin: ('g', Pitch('G4'), Pitch('D5'), 4),
    Clef.Treble:       ('g', Pitch('G4'), Pitch('B4'), 4),
    Clef.Soprano:      ('c', Pitch('C4'), Pitch('G4'), 3),
    Clef.MezzoSoprano: ('c', Pitch('C4'), Pitch('E4'), 3),
    Clef.Alto:         ('c', Pitch('C4'), Pitch('C4'), 3),
    Clef.Tenor:        ('c', Pitch('C4'), Pitch('A3'), 3),
    Clef.Baritone:     ('f', Pitch('F3'), Pitch('F3'), 2),
    Clef.Bass:         ('f', Pitch('F3'), Pitch('D3'), 2),
    Clef.Subbass:      ('f', Pitch('F3'), Pitch('B2'), 2),
    }

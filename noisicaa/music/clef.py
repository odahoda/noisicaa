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

# mypy: loose

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

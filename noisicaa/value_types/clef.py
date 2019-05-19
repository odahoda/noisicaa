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

import enum

from google.protobuf import message as protobuf

from . import proto_value
from . import value_types_pb2
from . import pitch


@enum.unique
class Clef(proto_value.ProtoValue, enum.Enum):
    FrenchViolin = 'french-violin'
    Treble = 'treble'
    Soprano = 'soprano'
    MezzoSoprano = 'mezzo-soprano'
    Alto = 'alto'
    Tenor = 'tenor'
    Baritone = 'baritone'
    Bass = 'bass'
    Subbass = 'subbass'

    def to_proto(self) -> value_types_pb2.Clef:
        return value_types_pb2.Clef(type={
            Clef.FrenchViolin: value_types_pb2.Clef.FrenchViolin,
            Clef.Treble: value_types_pb2.Clef.Treble,
            Clef.Soprano: value_types_pb2.Clef.Soprano,
            Clef.MezzoSoprano: value_types_pb2.Clef.MezzoSoprano,
            Clef.Alto: value_types_pb2.Clef.Alto,
            Clef.Tenor: value_types_pb2.Clef.Tenor,
            Clef.Baritone: value_types_pb2.Clef.Baritone,
            Clef.Bass: value_types_pb2.Clef.Bass,
            Clef.Subbass: value_types_pb2.Clef.Subbass,
        }[self])

    @classmethod
    def from_proto(cls, pb: protobuf.Message) -> 'Clef':
        if not isinstance(pb, value_types_pb2.Clef):
            raise TypeError(type(pb).__name__)
        return Clef({
            value_types_pb2.Clef.FrenchViolin: Clef.FrenchViolin,
            value_types_pb2.Clef.Treble: Clef.Treble,
            value_types_pb2.Clef.Soprano: Clef.Soprano,
            value_types_pb2.Clef.MezzoSoprano: Clef.MezzoSoprano,
            value_types_pb2.Clef.Alto: Clef.Alto,
            value_types_pb2.Clef.Tenor: Clef.Tenor,
            value_types_pb2.Clef.Baritone: Clef.Baritone,
            value_types_pb2.Clef.Bass: Clef.Bass,
            value_types_pb2.Clef.Subbass: Clef.Subbass,
        }[pb.type])

    @property
    def symbol(self) -> str:
        return _clef_data[self][0]

    @property
    def base_pitch(self) -> pitch.Pitch:
        return _clef_data[self][1]

    @property
    def center_pitch(self) -> pitch.Pitch:
        return _clef_data[self][2]

    @property
    def base_octave(self) -> int:
        return _clef_data[self][3]


# (symbol, base_pitch, center_pitch, base_octave)
_clef_data = {
    Clef.FrenchViolin: ('g', pitch.Pitch('G4'), pitch.Pitch('D5'), 4),
    Clef.Treble:       ('g', pitch.Pitch('G4'), pitch.Pitch('B4'), 4),
    Clef.Soprano:      ('c', pitch.Pitch('C4'), pitch.Pitch('G4'), 3),
    Clef.MezzoSoprano: ('c', pitch.Pitch('C4'), pitch.Pitch('E4'), 3),
    Clef.Alto:         ('c', pitch.Pitch('C4'), pitch.Pitch('C4'), 3),
    Clef.Tenor:        ('c', pitch.Pitch('C4'), pitch.Pitch('A3'), 3),
    Clef.Baritone:     ('f', pitch.Pitch('F3'), pitch.Pitch('F3'), 2),
    Clef.Bass:         ('f', pitch.Pitch('F3'), pitch.Pitch('D3'), 2),
    Clef.Subbass:      ('f', pitch.Pitch('F3'), pitch.Pitch('B2'), 2),
}

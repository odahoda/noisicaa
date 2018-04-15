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

from typing import Dict, List


class KeySignature(object):
    _signatures = {
        'C major':  [],
        'A minor':  [],
        'G major':  ['F#'],
        'E minor':  ['F#'],
        'D major':  ['F#', 'C#'],
        'B minor':  ['F#', 'C#'],
        'A major':  ['F#', 'C#', 'G#'],
        'F# minor': ['F#', 'C#', 'G#'],
        'E major':  ['F#', 'C#', 'G#', 'D#'],
        'C# minor': ['F#', 'C#', 'G#', 'D#'],
        'B major':  ['F#', 'C#', 'G#', 'D#', 'A#'],
        'G# minor': ['F#', 'C#', 'G#', 'D#', 'A#'],
        'F# major': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#'],
        'D# minor': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#'],
        'C# major': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'],
        'A# minor': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'],
        'F major':  ['Bb'],
        'D minor':  ['Bb'],
        'Bb major': ['Bb', 'Eb'],
        'G minor':  ['Bb', 'Eb'],
        'Eb major': ['Bb', 'Eb', 'Ab'],
        'C minor':  ['Bb', 'Eb', 'Ab'],
        'Ab major': ['Bb', 'Eb', 'Ab', 'Db'],
        'F minor':  ['Bb', 'Eb', 'Ab', 'Db'],
        'Db major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb'],
        'Bb minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb'],
        'Gb major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
        'Eb minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
        'Cb major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb'],
        'Ab minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb'],
    }  # type: Dict[str, List[str]]

    def __init__(self, name: str = 'C major') -> None:
        assert name in self._signatures, name
        self._name = name

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False

        if not isinstance(other, KeySignature):
            raise TypeError(
                "Can't compare %s to %s" % (type(self).__name__, type(other).__name__))

        return self.name == other.name

    def __repr__(self) -> str:
        return 'KeySignature("%s")' % self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def accidentals(self) -> List[str]:
        return self._signatures[self._name]

    @property
    def accidental_map(self) -> Dict[str, str]:
        acc_map = {v: '' for v in 'CDEFGAB'}
        for acc in self._signatures[self._name]:
            acc_map[acc[0]] = acc[1]
        return acc_map

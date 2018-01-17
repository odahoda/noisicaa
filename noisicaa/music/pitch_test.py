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

import unittest

from .pitch import Pitch


class PitchTest(unittest.TestCase):
    def test_from_string(self):
        p = Pitch('G#4')
        self.assertEqual(p.name, 'G#4')
        self.assertEqual(p.octave, 4)
        self.assertEqual(p.value, 'G')
        self.assertEqual(p.accidental, '#')

    def test_equal(self):
        self.assertEqual(Pitch('G#5'), Pitch('G#5'))
        self.assertNotEqual(Pitch('G#5'), Pitch('G#4'))
        self.assertNotEqual(Pitch('G#5'), Pitch('G5'))
        self.assertNotEqual(Pitch('G#5'), Pitch('A#5'))

    def test_sort(self):
        self.assertGreater(Pitch('G#5'), Pitch('G5'))
        self.assertGreater(Pitch('A5'), Pitch('G5'))
        self.assertGreater(Pitch('C6'), Pitch('B5'))
        self.assertGreater(Pitch('G6'), Pitch('G5'))

    def test_transposed(self):
        p = Pitch('G#4')
        self.assertEqual(p.transposed(octaves=-1), Pitch('G#3'))


if __name__ == '__main__':
    unittest.main()

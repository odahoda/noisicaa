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

from noisidev import unittest
from .key_signature import KeySignature


class KeySignatureTest(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(KeySignature(name='C major'),
                         KeySignature(name='C major'))
        self.assertNotEqual(KeySignature(name='C major'),
                            KeySignature(name='G major'))

    def test_compare_with_bad_class(self):
        with self.assertRaises(TypeError):
            # pylint: disable=expression-not-assigned
            KeySignature() == 'foo'

    def test_preset_names(self):
        self.assertEqual(KeySignature(name='G major').accidentals, ['F#'])
        self.assertEqual(KeySignature(name='G minor').accidentals, ['Bb', 'Eb'])

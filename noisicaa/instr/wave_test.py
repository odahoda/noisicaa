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

import os.path

from noisidev import unittest
from . import wave


class WaveFileTest(unittest.TestCase):
    def test_foo(self):
        w = wave.WaveFile()
        w.parse(os.path.join(unittest.TESTDATA_DIR, 'test1.wav'))
        self.assertEqual(w.data_format, 'pcm')
        self.assertEqual(w.channels, 2)
        self.assertEqual(w.sample_rate, 44100)
        self.assertEqual(w.bits_per_sample, 16)
        self.assertEqual(w.num_samples, 9450)

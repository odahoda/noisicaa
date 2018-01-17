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

import os.path
import unittest

import numpy

from . import sndfile

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')

class SndFileTest(unittest.TestCase):
    def test_properties(self):
        with sndfile.SndFile(os.path.join(TEST_DATA_DIR, 'test1.wav')) as sf:
            self.assertEqual(sf.num_channels, 2)
            self.assertEqual(sf.num_samples, 9450)
            self.assertEqual(sf.sample_rate, 44100)
            self.assertEqual(sf.file_format, sndfile.FileFormat.WAV)
            self.assertEqual(sf.encoding, sndfile.Encoding.PCM_16)

    def test_get_samples(self):
        with sndfile.SndFile(os.path.join(TEST_DATA_DIR, 'test1.wav')) as sf:
            smpls = sf.get_samples()
            self.assertIsInstance(smpls, numpy.ndarray)
            self.assertEqual(smpls.dtype, numpy.float32)
            self.assertEqual(smpls.shape, (9450, 2))

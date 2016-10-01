#!/usr/bin/python3

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

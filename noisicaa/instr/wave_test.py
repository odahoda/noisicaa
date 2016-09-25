#!/usr/bin/python3

import os.path
import unittest
from unittest import mock

from . import wave

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')

class WaveFileTest(unittest.TestCase):
    def test_foo(self):
        w = wave.WaveFile().parse(os.path.join(TEST_DATA_DIR, 'test1.wav'))
        self.assertEqual(w.data_format, 'pcm')
        self.assertEqual(w.channels, 2)
        self.assertEqual(w.sample_rate, 44100)
        self.assertEqual(w.bits_per_sample, 16)
        self.assertEqual(w.num_samples, 9450)


if __name__ == '__main__':
    unittest.main()

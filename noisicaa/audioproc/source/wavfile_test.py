#!/usr/bin/python3

import os.path
import unittest

from . import sourcetest
from . import wavfile

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'testdata')

class WavFileTest(sourcetest.SourceTest):
    def make_node(self):
        return wavfile.WavFileSource(os.path.join(TESTDATA_DIR, 'ping.wav'))


if __name__ == '__main__':
    unittest.main()

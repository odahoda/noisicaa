#!/usr/bin/python3

import os.path
import unittest

from noisicaa.audioproc import data
from . import wavfile

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'testdata')

class WavFileSourceTest(unittest.TestCase):
    def test_basic(self):
        node = wavfile.WavFileSource(
            id='test',
            path=os.path.join(TESTDATA_DIR, 'ping.wav'))
        node.setup()
        try:
            buf_l = bytearray(1024)
            buf_r = bytearray(1024)
            node.connect_port('out:left', buf_l)
            node.connect_port('out:right', buf_r)

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 256
            node.run(ctxt)

        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

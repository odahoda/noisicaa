#!/usr/bin/python3

import os.path
import unittest

from noisicaa import constants
from noisicaa.audioproc import data
from . cimport wavfile
from ..vm cimport buffers

TESTDATA_DIR = os.path.join(constants.ROOT, 'audioproc', 'testdata')


class WavFileSourceTest(unittest.TestCase):
    def test_basic(self):
        cdef:
            wavfile.WavFileSource node
            buffers.Buffer buf_l
            buffers.Buffer buf_r

        node = wavfile.WavFileSource(
            id='test',
            path=os.path.join(TESTDATA_DIR, 'ping.wav'))
        node.setup()
        try:
            buf_l = buffers.Buffer(buffers.FloatArray(256))
            buf_r = buffers.Buffer(buffers.FloatArray(256))
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

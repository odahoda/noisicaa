#!/usr/bin/python3

import asynctest
import os.path
import unittest

from noisicaa.audioproc import data
from . import wavfile

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'testdata')

class WavFileSourceTest(asynctest.TestCase):
    async def test_basic(self):
        node = wavfile.WavFileSource(
            self.loop, os.path.join(TESTDATA_DIR, 'ping.wav'))
        await node.setup()
        try:
            buf_l = bytearray(1024)
            buf_r = bytearray(1024)
            node.connect_port('out_left', buf_l)
            node.connect_port('out_right', buf_r)

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 256
            node.run(ctxt)

        finally:
            await node.cleanup()


if __name__ == '__main__':
    unittest.main()

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
            buf = bytearray(2048)
            node.connect_port('out_left', buf, 0)
            node.connect_port('out_right', buf, 1024)

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 256
            node.run(ctxt)

        finally:
            await node.cleanup()


if __name__ == '__main__':
    unittest.main()

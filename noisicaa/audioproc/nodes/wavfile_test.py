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
            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 512
            node.collect_inputs(ctxt)
            node.run(ctxt)
        finally:
            await node.cleanup()


if __name__ == '__main__':
    unittest.main()

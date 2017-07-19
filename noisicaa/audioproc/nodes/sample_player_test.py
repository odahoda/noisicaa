#!/usr/bin/python3

import unittest

from noisicaa.audioproc import data
from noisicaa.bindings import lv2
from . import sample_player


class SamplePlayerTest(unittest.TestCase):
    def test_basic(self):
        node = sample_player.SamplePlayer(
            sample_path='/usr/share/sounds/freedesktop/stereo/bell.oga')
        node.setup()
        try:
            buf_in = bytearray(10240)
            buf_out_l = bytearray(1024)
            buf_out_r = bytearray(1024)
            node.connect_port('in', buf_in)
            node.connect_port('out:left', buf_out_l)
            node.connect_port('out:right', buf_out_r)

            forge = lv2.AtomForge(lv2.static_mapper)
            forge.set_buffer(buf_in, 10240)
            with forge.sequence():
                forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
                forge.write_midi_event(128, bytes([0x80, 60, 0]), 3)

            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 256
            node.run(ctxt)

        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

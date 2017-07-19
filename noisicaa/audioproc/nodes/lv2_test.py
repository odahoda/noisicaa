#!/usr/bin/python3

import unittest
import os
import os.path

from noisicaa import constants
from noisicaa import node_db
from noisicaa.audioproc import data
from . import lv2

class LV2Test(unittest.TestCase):
    def test_foo(self):
        description = node_db.NodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ],
            parameters=[
                node_db.InternalParameterDescription(
                    name='uri', value='http://lv2plug.in/plugins/eg-amp'),
                node_db.FloatParameterDescription(
                    name='gain',
                    display_name='Gain',
                    default=0.0,
                    min=-90.0,
                    max=24.0),
            ])
        ctxt = data.FrameContext()
        ctxt.sample_pos = 0
        ctxt.duration = 256

        buf_in = bytearray(1024)
        buf_out = bytearray(1024)

        node = lv2.LV2(description=description)
        node.setup()
        try:
            node.connect_port('in', buf_in)
            node.connect_port('out', buf_out)
            node.run(ctxt)
        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python3

import asynctest
import os
import os.path

from noisicaa import constants
from noisicaa import node_db
from noisicaa.audioproc import data
from . import lv2

class LV2Test(asynctest.TestCase):
    async def test_foo(self):
        description = node_db.NodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input,
                    channels='mono'),
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output,
                    channels='mono'),
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
        ctxt.duration = 1024

        node = lv2.LV2(self.loop, description)
        await node.setup()
        try:
            node.collect_inputs(ctxt)
            node.run(ctxt)
        finally:
            await node.cleanup()


if __name__ == '__main__':
    unittest.main()
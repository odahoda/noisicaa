#!/usr/bin/python3

import asynctest

from noisicaa.audioproc import data


class SourceTest(asynctest.TestCase):
    def make_node(self):
        raise NotImplementedError

    async def testBasicRun(self):
        node = self.make_node()
        await node.setup()
        try:
            ctxt = data.FrameContext()
            ctxt.sample_pos = 0
            ctxt.duration = 512
            node.collect_inputs(ctxt)
            node.run(ctxt)
        finally:
            await node.cleanup()

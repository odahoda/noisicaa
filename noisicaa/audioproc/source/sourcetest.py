#!/usr/bin/python3

import asynctest


class SourceTest(asynctest.TestCase):
    def make_node(self):
        raise NotImplementedError

    async def testBasicRun(self):
        node = self.make_node()
        await node.setup()
        try:
            node.collect_inputs()
            node.run(0)
        finally:
            await node.cleanup()

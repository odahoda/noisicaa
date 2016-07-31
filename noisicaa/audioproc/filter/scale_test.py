#!/usr/bin/python3

import unittest

import asynctest

from ..pipeline import Pipeline
from ..source.whitenoise import WhiteNoiseSource
from . import scale


class ScaleTest(asynctest.TestCase):
    async def testBasicRun(self):
        pipeline = Pipeline()

        source = WhiteNoiseSource()
        pipeline.add_node(source)

        node = scale.Scale(self.loop, 0.5)
        pipeline.add_node(node)
        node.inputs['in'].connect(source.outputs['out'])
        await node.setup()
        try:
            node.collect_inputs()
            node.run(0)
        finally:
            await node.cleanup()


if __name__ == '__main__':
    unittest.main()

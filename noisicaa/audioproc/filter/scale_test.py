#!/usr/bin/python3

import unittest

from ..pipeline import Pipeline
from ..source.whitenoise import WhiteNoiseSource
from . import scale


class ScaleTest(unittest.TestCase):
    def testBasicRun(self):
        pipeline = Pipeline()

        source = WhiteNoiseSource()
        pipeline.add_node(source)

        node = scale.Scale(0.5)
        pipeline.add_node(node)
        node.inputs['in'].connect(source.outputs['out'])
        node.outputs['out'].connect()
        node.setup()
        try:
            node.outputs['out'].start()
            self.assertEqual(node.outputs['out'].buffered_duration, 0)
            node.run()
            self.assertGreater(node.outputs['out'].buffered_duration, 0)
        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

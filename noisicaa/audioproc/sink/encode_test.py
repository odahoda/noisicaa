#!/usr/bin/python3

import unittest

from ..pipeline import Pipeline
from ..source.whitenoise import WhiteNoiseSource
from . import encode


class PyAudioTest(unittest.TestCase):
    def test_flac(self):
        pipeline = Pipeline()

        source = WhiteNoiseSource()
        source.setup()
        pipeline.add_node(source)

        node = encode.EncoderSink('flac', '/tmp/foo.flac')
        node.setup()
        pipeline.add_node(node)
        node.inputs['in'].connect(source.outputs['out'])
        try:
            node.collect_inputs()
            node.run(0)
        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

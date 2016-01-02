#!/usr/bin/python3

import unittest

from ..pipeline import Pipeline
from ..source.whitenoise import WhiteNoiseSource
from . import encode


class PyAudioTest(unittest.TestCase):
    def test_flac(self):
        pipeline = Pipeline()

        source = WhiteNoiseSource()
        pipeline.add_node(source)

        node = encode.EncoderSink('flac', '/tmp/foo.flac')
        pipeline.add_node(node)
        node.inputs['in'].connect(source.outputs['out'])
        node.setup()
        try:
            node.start()
            node.consume(4096)
            node.stop()
        finally:
            node.cleanup()


if __name__ == '__main__':
    unittest.main()

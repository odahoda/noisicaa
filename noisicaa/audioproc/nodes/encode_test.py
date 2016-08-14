#!/usr/bin/python3

import unittest

import asynctest

from ..pipeline import Pipeline
from . import encode


# class EncodeTest(asynctest.TestCase):
#     async def test_flac(self):
#         pipeline = Pipeline()

#         source = WhiteNoiseSource(self.loop)
#         await source.setup()
#         pipeline.add_node(source)

#         node = encode.EncoderSink(self.loop, 'flac', '/tmp/foo.flac')
#         await node.setup()
#         pipeline.add_node(node)
#         node.inputs['in'].connect(source.outputs['out'])
#         try:
#             node.collect_inputs()
#             node.run(0)
#         finally:
#             await node.cleanup()


if __name__ == '__main__':
    unittest.main()

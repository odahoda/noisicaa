#!/usr/bin/python3

import unittest

from . import encode


# class EncodeTest(unitctest.TestCase):
#     def test_flac(self):
#         pipeline = Pipeline()

#         source = WhiteNoiseSource(self.loop)
#         source.setup()
#         pipeline.add_node(source)

#         node = encode.EncoderSink(self.loop, 'flac', '/tmp/foo.flac')
#         node.setup()
#         pipeline.add_node(node)
#         node.inputs['in'].connect(source.outputs['out'])
#         try:
#             node.collect_inputs()
#             node.run(0)
#         finally:
#             node.cleanup()


if __name__ == '__main__':
    unittest.main()

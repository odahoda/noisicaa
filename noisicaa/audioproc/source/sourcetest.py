#!/usr/bin/python3

import unittest


class SourceTest(unittest.TestCase):
    def make_node(self):
        raise NotImplementedError

    def testBasicRun(self):
        node = self.make_node()
        node.outputs['out'].connect()
        node.setup()
        try:
            node.outputs['out'].start()
            self.assertEqual(node.outputs['out'].buffered_duration, 0)
            node.run()
            self.assertGreater(node.outputs['out'].buffered_duration, 0)
        finally:
            node.cleanup()

#!/usr/bin/python3

import unittest


class SourceTest(unittest.TestCase):
    def make_node(self):
        raise NotImplementedError

    def testBasicRun(self):
        node = self.make_node()
        node.setup()
        try:
            node.collect_inputs()
            node.run(0)
        finally:
            node.cleanup()

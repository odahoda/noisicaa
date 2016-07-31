#!/usr/bin/python3

import unittest

import asynctest

from .exceptions import Error
from .node import Node
from .ports import InputPort, OutputPort
from . import pipeline


class PipelineTest(asynctest.TestCase):
    async def testSortedNodes(self):
        p = pipeline.Pipeline()

        n1 = Node(self.loop)
        p.add_node(n1)
        n1.add_output(OutputPort('p'))

        n2 = Node(self.loop)
        p.add_node(n2)
        n2.add_output(OutputPort('p'))

        n3 = Node(self.loop)
        p.add_node(n3)
        n3.add_input(InputPort('p1'))
        n3.add_input(InputPort('p2'))
        n3.inputs['p1'].connect(n1.outputs['p'])
        n3.inputs['p2'].connect(n2.outputs['p'])
        n3.add_output(OutputPort('p'))

        n4 = Node(self.loop)
        p.add_node(n4)
        n4.add_output(OutputPort('p'))

        n5 = Node(self.loop)
        p.add_node(n5)
        n5.add_input(InputPort('p1'))
        n5.add_input(InputPort('p2'))
        n5.inputs['p1'].connect(n3.outputs['p'])
        n5.inputs['p2'].connect(n4.outputs['p'])

        visited = set()
        for n in p.sorted_nodes:
            for pn in n.parent_nodes:
                self.assertIn(pn, visited)
            visited.add(n)

    async def testCyclicGraph(self):
        p = pipeline.Pipeline()

        n1 = Node(self.loop)
        p.add_node(n1)
        n1.add_output(OutputPort('p'))

        n2 = Node(self.loop)
        p.add_node(n2)
        n2.add_input(InputPort('p1'))
        n2.add_input(InputPort('p2'))
        n2.add_output(OutputPort('p'))

        n3 = Node(self.loop)
        p.add_node(n3)
        n3.add_input(InputPort('p'))
        n3.add_output(OutputPort('p1'))
        n3.add_output(OutputPort('p2'))

        n4 = Node(self.loop)
        p.add_node(n4)
        n4.add_input(InputPort('p'))
        n4.add_output(OutputPort('p'))

        n2.inputs['p1'].connect(n1.outputs['p'])
        n2.inputs['p2'].connect(n3.outputs['p2'])
        n3.inputs['p'].connect(n2.outputs['p'])
        n4.inputs['p'].connect(n3.outputs['p1'])

        with self.assertRaises(Error):
            p.sorted_nodes  # pylint: disable=W0104


if __name__ == '__main__':
    unittest.main()

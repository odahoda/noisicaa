#!/usr/bin/python3

import logging
import unittest

import asynctest

from .. import nodes
from . import compiler
from . import graph

logger = logging.getLogger(__name__)


class CompilerTest(asynctest.TestCase):
    async def test_foo(self):
        g = graph.PipelineGraph()

        node1 = nodes.PassThru(self.loop)
        g.add_node(node1)

        node2 = nodes.PassThru(self.loop)
        g.add_node(node2)
        node2.inputs['in'].connect(node1.outputs['out'])

        node3 = nodes.Sink(self.loop)
        g.add_node(node3)
        node3.inputs['audio_left'].connect(node1.outputs['out'])
        node3.inputs['audio_left'].connect(node2.outputs['out'])
        node3.inputs['audio_right'].connect(node2.outputs['out'])

        comp = compiler.Compiler(graph=g, frame_size=64)
        ast = comp.build_ast()
        print(ast.dump())


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python3

import logging
import unittest

import asynctest

from .. import nodes
from . import compiler
from . import graph

logger = logging.getLogger(__name__)


class CompilerTest(asynctest.TestCase):
    def _build_graph(self):
        g = graph.PipelineGraph()

        node1 = nodes.PassThru(self.loop)
        g.add_node(node1)

        node2 = nodes.PassThru(self.loop)
        g.add_node(node2)
        node2.inputs['in:left'].connect(node1.outputs['out:left'])
        node2.inputs['in:right'].connect(node1.outputs['out:right'])

        node3 = nodes.Sink(self.loop)
        g.add_node(node3)
        node3.inputs['in:left'].connect(node1.outputs['out:left'])
        node3.inputs['in:left'].connect(node2.outputs['out:left'])
        node3.inputs['in:right'].connect(node2.outputs['out:right'])

        return g

    async def test_build_ast(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g, frame_size=64)
        ast = comp.build_ast()
        print(ast.dump())

    async def test_build_symbol_table(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g, frame_size=64)
        ast = comp.build_ast()
        symbol_table = comp.build_symbol_table(ast)
        print(symbol_table.dump())

    async def test_build_spec(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g, frame_size=64)
        ast = comp.build_ast()
        symbol_table = comp.build_symbol_table(ast)
        spec = comp.build_spec(ast, symbol_table)
        print(spec.dump())


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python3

import logging
import unittest

import noisicore
from noisicaa import node_db
from .. import node
from . import compiler
from . import graph

logger = logging.getLogger(__name__)


class CompilerTest(unittest.TestCase):
    def setUp(self):
        self.host_data = noisicore.HostData()

    def _build_graph(self):
        g = graph.PipelineGraph()

        description1 = node_db.ProcessorDescription(
            processor_name='null',
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])
        node1 = node.ProcessorNode(
            id='node1',
            host_data=self.host_data,
            description=description1)
        node1.setup()
        g.add_node(node1)

        description2 = node_db.ProcessorDescription(
            processor_name='null',
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])
        node2 = node.ProcessorNode(
            id='node2',
            host_data=self.host_data,
            description=description2)
        node2.setup()
        g.add_node(node2)
        node2.inputs['in:left'].connect(node1.outputs['out:left'])
        node2.inputs['in:right'].connect(node1.outputs['out:right'])

        description3 = node_db.ProcessorDescription(
            processor_name='null',
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
            ])
        node3 = node.ProcessorNode(
            id='sink',
            host_data=self.host_data,
            description=description3)
        node3.setup()
        g.add_node(node3)
        node3.inputs['in:left'].connect(node1.outputs['out:left'])
        node3.inputs['in:left'].connect(node2.outputs['out:left'])
        node3.inputs['in:right'].connect(node2.outputs['out:right'])

        return g

    def test_build_ast(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g)
        ast = comp.build_ast()
        print(ast.dump())

    def test_build_spec(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g)
        ast = comp.build_ast()
        spec = comp.build_spec(ast)
        print(spec.dump())


if __name__ == '__main__':
    unittest.main()

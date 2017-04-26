#!/usr/bin/python3

import logging
import struct
import threading
import time
import unittest

import asynctest

from noisicaa import node_db
from . import backend
from . import data
from . import pipeline_vm
from . import resample
from . import nodes
from . import compiler

logger = logging.getLogger(__name__)


class CompilerTest(asynctest.TestCase):
    async def test_foo(self):
        graph = pipeline_vm.PipelineGraph()

        node1 = nodes.PassThru(self.loop)
        graph.add_node(node1)

        node2 = nodes.PassThru(self.loop)
        graph.add_node(node2)
        node2.inputs['in'].connect(node1.outputs['out'])

        node3 = nodes.Sink(self.loop)
        graph.add_node(node3)
        node3.inputs['audio_left'].connect(node1.outputs['out'])
        node3.inputs['audio_left'].connect(node2.outputs['out'])
        node3.inputs['audio_right'].connect(node2.outputs['out'])

        comp = compiler.Compiler(graph)
        ast = comp.build_ast()
        print(ast.dump())


if __name__ == '__main__':
    unittest.main()

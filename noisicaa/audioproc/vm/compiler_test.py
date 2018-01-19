#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging

from noisidev import unittest
from noisicaa.audioproc import vm
from noisicaa import node_db
from .. import node
from . import compiler
from . import graph

logger = logging.getLogger(__name__)


class CompilerTest(unittest.TestCase):
    def setup_testcase(self):
        self.host_data = vm.HostData()

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
                node_db.KRateControlPortDescription(
                    name='gain',
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

    def test_build_spec(self):
        g = self._build_graph()
        comp = compiler.Compiler(graph=g)
        spec = comp.build_spec()
        logger.info(spec.dump())

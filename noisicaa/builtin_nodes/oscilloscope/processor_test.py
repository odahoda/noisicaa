# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

from noisidev import unittest
from noisidev import unittest_processor_mixins
from noisicaa.audioproc.public import node_parameters_pb2
from . import processor_pb2


class ProcessorOscilloscopeTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def test_process_block(self):
        self.node_description = self.node_db['builtin://oscilloscope']
        self.create_processor()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.oscilloscope_spec]
        spec.foo = 1
        self.processor.set_parameters(params)

        self.process_block()

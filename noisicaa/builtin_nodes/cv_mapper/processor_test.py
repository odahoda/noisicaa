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


class ProcessorCVMapperTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def test_process_block(self):
        self.node_description = self.node_db['builtin://cv-mapper']
        self.create_processor()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.cv_mapper_spec]
        spec.transfer_function.input_min = -1.0
        spec.transfer_function.input_max = 1.0
        spec.transfer_function.output_min = -1.0
        spec.transfer_function.output_max = 1.0
        spec.transfer_function.fixed.value = 0.5
        self.processor.set_parameters(params)

        self.process_block()
        self.assertBufferAllEqual('out', 0.5)

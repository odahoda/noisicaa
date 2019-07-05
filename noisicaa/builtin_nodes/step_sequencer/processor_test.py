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
from noisicaa import node_db
from noisicaa.audioproc.public import node_parameters_pb2
from . import model_pb2
from . import processor_pb2


class ProcessorStepSequencerTest(
        unittest_processor_mixins.ProcessorTestMixin,
        unittest.TestCase):
    def test_process_block(self):
        self.node_description = self.node_db['builtin://step-sequencer']
        self.node_description.ports.add(
            name='channel1',
            direction=node_db.PortDescription.OUTPUT,
            type=node_db.PortDescription.ARATE_CONTROL,
        )

        self.create_processor()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.step_sequencer_spec]
        spec.num_steps = 4
        spec.time_synched = False
        channel1_spec = spec.channels.add()
        channel1_spec.type = model_pb2.StepSequencerChannel.VALUE
        channel1_spec.step_value.extend([1.0, 0.0, 0.0, 0.0])
        self.processor.set_parameters(params)

        self.fill_buffer('tempo', 8.0)

        self.process_block()
        self.assertBufferIsNotQuiet('channel1')

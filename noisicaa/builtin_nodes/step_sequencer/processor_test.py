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
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import node_db
from noisicaa.audioproc.public import node_parameters_pb2
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import model_pb2
from . import processor_pb2


class ProcessorStepSequencerTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):

    def test_value(self):
        plugin_uri = 'builtin://step-sequencer'

        node_desc = node_db.NodeDescription()
        node_desc.CopyFrom(self.node_db[plugin_uri])
        node_desc.ports.add(
            name='channel1',
            direction=node_db.PortDescription.OUTPUT,
            type=node_db.PortDescription.ARATE_CONTROL,
        )

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.step_sequencer_spec]
        spec.num_steps = 4
        spec.time_synched = False
        channel1_spec = spec.channels.add()
        channel1_spec.type = model_pb2.StepSequencerChannel.VALUE
        channel1_spec.step_value.extend([1.0, 0.0, 0.0, 0.0])
        proc.set_parameters(params)

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        tempo = buffer_mgr.allocate('tempo', buffers.PyFloatAudioBlockBuffer())
        channel1_out = buffer_mgr.allocate('channel1', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('tempo'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('channel1'))

        for i in range(self.host_system.block_size):
            channel1_out[i] = 0.0
            tempo[0] = 8.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(any(v != 0.0 for v in channel1_out), [v for v in channel1_out])

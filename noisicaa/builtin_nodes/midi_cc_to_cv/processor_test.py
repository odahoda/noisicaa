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
from noisicaa import lv2
from noisicaa.audioproc.public import node_parameters_pb2
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_pb2


class ProcessorMidiCCtoCVTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):

    def test_value(self):
        plugin_uri = 'builtin://midi-cc-to-cv'
        node_desc = self.node_db[plugin_uri]
        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        params = node_parameters_pb2.NodeParameters()
        spec = params.Extensions[processor_pb2.midi_cc_to_cv_spec]
        channel_spec = spec.channels.add()
        channel_spec.midi_channel = 1
        channel_spec.midi_controller = 12
        channel_spec.initial_value = 0
        channel_spec.min_value = 1.0
        channel_spec.max_value = 2.0
        channel_spec.log_scale = False
        proc.set_parameters(params)

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        buffer_mgr.allocate('in', buffers.PyAtomDataBuffer())
        cv_out = buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('in'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('out'))

        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(buffer_mgr.data('in'), 10240)
        with forge.sequence():
            pass
        for i in range(self.host_system.block_size):
            cv_out[i] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(all(v != 1.0 for v in cv_out), [v for v in cv_out[:32]])

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

import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import node_db
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor


class ProcessorOscillatorTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def test_json(self):
        node_db.faust_json_to_node_description(
            os.path.join(os.path.dirname(__file__), 'processor.json'))

    def test_oscillator(self):
        plugin_uri = 'builtin://oscillator'
        node_description = self.node_db[plugin_uri]

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_description)
        proc.setup()

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        freq = buffer_mgr.allocate('freq', buffers.PyFloatAudioBlockBuffer())
        out = buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())
        waveform = buffer_mgr.allocate('waveform', buffers.PyFloatControlValueBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('freq'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('out'))
        proc.connect_port(ctxt, 2, buffer_mgr.data('waveform'))

        for i in range(self.host_system.block_size):
            freq[i] = 440
            out[i] = 0.0
        waveform[0] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper
        self.assertTrue(any(v != 0.0 for v in out))

        proc.cleanup()

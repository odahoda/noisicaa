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

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from . import block_context
from . import buffers
from . import processor


class ProcessorTrackMixerTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def test_track_mixer(self):
        plugin_uri = 'builtin://track_mixer'
        node_description = self.node_db[plugin_uri]

        proc = processor.PyProcessor('test_node', self.host_system, node_description)
        proc.setup()

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        audio_l_in = buffer_mgr.allocate('in:left', buffers.PyFloatAudioBlockBuffer())
        audio_r_in = buffer_mgr.allocate('in:right', buffers.PyFloatAudioBlockBuffer())
        audio_l_out = buffer_mgr.allocate('out:left', buffers.PyFloatAudioBlockBuffer())
        audio_r_out = buffer_mgr.allocate('out:right', buffers.PyFloatAudioBlockBuffer())
        gain = buffer_mgr.allocate('gain', buffers.PyFloatControlValueBuffer())
        muted = buffer_mgr.allocate('muted', buffers.PyFloatControlValueBuffer())
        pan = buffer_mgr.allocate('pan', buffers.PyFloatControlValueBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('in:left'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('in:right'))
        proc.connect_port(ctxt, 2, buffer_mgr.data('out:left'))
        proc.connect_port(ctxt, 3, buffer_mgr.data('out:right'))
        proc.connect_port(ctxt, 4, buffer_mgr.data('gain'))
        proc.connect_port(ctxt, 5, buffer_mgr.data('muted'))
        proc.connect_port(ctxt, 6, buffer_mgr.data('pan'))

        for i in range(self.host_system.block_size):
            audio_l_in[i] = 1.0
            audio_r_in[i] = -1.0
            audio_l_out[i] = 0.0
            audio_r_out[i] = 0.0
        gain[0] = 0.0
        muted[0] = 0.0
        pan[0] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper
        self.assertTrue(any(v != 0.0 for v in audio_l_out))
        self.assertTrue(any(v != 0.0 for v in audio_r_out))

        muted[0] = 1.0
        proc.process_block(ctxt, None)  # TODO: pass time_mapper
        self.assertTrue(any(v == 0.0 for v in audio_l_out))
        self.assertTrue(any(v == 0.0 for v in audio_r_out))

        proc.cleanup()

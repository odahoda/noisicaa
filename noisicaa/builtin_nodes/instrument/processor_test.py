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

import os
import os.path

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import lv2
from noisicaa.audioproc.public import instrument_spec_pb2
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_messages


class ProcessorInstrumentTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):

    def playback_test(self, instrument_spec):
        plugin_uri = 'builtin://instrument'
        node_desc = self.node_db[plugin_uri]

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        proc.handle_message(processor_messages.change_instrument('test_node', instrument_spec))

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        buffer_mgr.allocate('in', buffers.PyAtomDataBuffer())
        audio_l_out = buffer_mgr.allocate('out:left', buffers.PyFloatAudioBlockBuffer())
        audio_r_out = buffer_mgr.allocate('out:right', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('in'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('out:left'))
        proc.connect_port(ctxt, 2, buffer_mgr.data('out:right'))

        urid_mapper = lv2.DynamicURIDMapper()

        # run once empty to give csound some chance to initialize the ftable
        forge = lv2.AtomForge(urid_mapper)
        forge.set_buffer(buffer_mgr.data('in'), 10240)
        with forge.sequence():
            pass

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        forge = lv2.AtomForge(urid_mapper)
        forge.set_buffer(buffer_mgr.data('in'), 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        for i in range(self.host_system.block_size):
            audio_l_out[i] = 0.0
            audio_r_out[i] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(any(v != 0.0 for v in audio_l_out))
        self.assertTrue(any(v != 0.0 for v in audio_r_out))

    def test_sample(self):
        self.playback_test(
            instrument_spec_pb2.InstrumentSpec(
                sample=instrument_spec_pb2.SampleInstrumentSpec(
                    path=os.path.join(unittest.TESTDATA_DIR, 'snare.wav'))))

    def test_sf2(self):
        self.playback_test(
            instrument_spec_pb2.InstrumentSpec(
                sf2=instrument_spec_pb2.SF2InstrumentSpec(
                    path=os.path.join(unittest.TESTDATA_DIR, 'sf2test.sf2'),
                    bank=0,
                    preset=0)))

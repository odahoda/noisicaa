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

import textwrap

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import lv2
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_messages


class ProcessorCustomCSoundTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)
        self.ctxt = block_context.PyBlockContext()

    def create_proc(self, orchestra, score):
        node_desc = self.node_db['builtin://custom-csound']

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        proc.handle_message(processor_messages.set_script('test_node', orchestra, score))

        audio_l_in = self.buffer_mgr.allocate('in:left', buffers.PyFloatAudioBlockBuffer())
        audio_r_in = self.buffer_mgr.allocate('in:right', buffers.PyFloatAudioBlockBuffer())
        ctrl = self.buffer_mgr.allocate('ctrl', buffers.PyFloatControlValueBuffer())
        self.buffer_mgr.allocate('ev', buffers.PyAtomDataBuffer())
        audio_l_out = self.buffer_mgr.allocate('out:left', buffers.PyFloatAudioBlockBuffer())
        audio_r_out = self.buffer_mgr.allocate('out:right', buffers.PyFloatAudioBlockBuffer())

        # clear all buffers
        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(self.buffer_mgr.data('ev'), 10240)
        with forge.sequence():
            pass
        ctrl[0] = 0.0
        for i in range(self.host_system.block_size):
            audio_l_in[i] = 0.0
            audio_r_in[i] = 0.0
            audio_l_out[i] = 0.0
            audio_r_out[i] = 0.0


        proc.connect_port(self.ctxt, 0, self.buffer_mgr.data('in:left'))
        proc.connect_port(self.ctxt, 1, self.buffer_mgr.data('in:right'))
        proc.connect_port(self.ctxt, 2, self.buffer_mgr.data('ctrl'))
        proc.connect_port(self.ctxt, 3, self.buffer_mgr.data('ev'))
        proc.connect_port(self.ctxt, 4, self.buffer_mgr.data('out:left'))
        proc.connect_port(self.ctxt, 5, self.buffer_mgr.data('out:right'))

        return proc

    def test_synth(self):
        orchestra = textwrap.dedent('''\
            instr 1
              gaOutLeft = 1.0
              gaOutRight = 1.0
            endin
            ''')
        score = textwrap.dedent('''\
            e 10000
            ''')
        proc = self.create_proc(orchestra, score)

        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(self.buffer_mgr.data('ev'), 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        # The instrument only gets active with one cycle delay, so the first 32 samples a silence.
        # Turning it off though works instantaneously.
        audio_l_out = self.buffer_mgr['out:left']
        self.assertTrue(all(v == 0.0 for v in audio_l_out[:32]))
        self.assertTrue(all(v == 1.0 for v in audio_l_out[32:64]))
        self.assertTrue(all(v == 0.0 for v in audio_l_out[64:]))
        audio_r_out = self.buffer_mgr['out:right']
        self.assertTrue(all(v == 0.0 for v in audio_r_out[:32]))
        self.assertTrue(all(v == 1.0 for v in audio_r_out[32:64]))
        self.assertTrue(all(v == 0.0 for v in audio_r_out[64:]))

    def test_filter(self):
        orchestra = textwrap.dedent('''\
            instr 1
              gaOutLeft = gkCtrl * gaInLeft
              gaOutRight = gkCtrl * gaInRight
            endin
            ''')
        score = textwrap.dedent('''\
            i1 0 -1
            e 10000
            ''')
        proc = self.create_proc(orchestra, score)

        audio_l_in = self.buffer_mgr['in:left']
        audio_r_in = self.buffer_mgr['in:right']
        for i in range(self.host_system.block_size):
            audio_l_in[i] = 1.0
            audio_r_in[i] = 1.0
        self.buffer_mgr['ctrl'][0] = 0.5

        proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        # The instrument only gets active with one cycle delay, so the first 32 samples a silence.
        audio_l_out = self.buffer_mgr['out:left']
        self.assertTrue(all(v == 0.0 for v in audio_l_out[:32]))
        self.assertTrue(all(v == 0.5 for v in audio_l_out[32:]))
        audio_r_out = self.buffer_mgr['out:right']
        self.assertTrue(all(v == 0.0 for v in audio_r_out[:32]))
        self.assertTrue(all(v == 0.5 for v in audio_r_out[32:]))

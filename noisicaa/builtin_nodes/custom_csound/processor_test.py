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

import textwrap

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa import node_db
from noisicaa import lv2
from noisicaa.audioproc.public import node_parameters_pb2
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import processor
from . import processor_pb2


class ProcessorCustomCSoundTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def setup_testcase(self):
        self.buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)
        self.ctxt = block_context.PyBlockContext()

    def create_proc(self, orchestra, score):
        node_desc = self.node_db['builtin://custom-csound']
        node_desc.ports.add(
            name='in',
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.INPUT)
        node_desc.ports.add(
            name='out',
            type=node_db.PortDescription.AUDIO,
            direction=node_db.PortDescription.OUTPUT)
        node_desc.ports.add(
            name='ctrl',
            type=node_db.PortDescription.KRATE_CONTROL,
            direction=node_db.PortDescription.INPUT)
        node_desc.ports.add(
            name='ev',
            type=node_db.PortDescription.EVENTS,
            direction=node_db.PortDescription.INPUT)

        proc = processor.PyProcessor('realm', 'test_node', self.host_system, node_desc)
        proc.setup()

        params = node_parameters_pb2.NodeParameters()
        csound_params = params.Extensions[processor_pb2.custom_csound_parameters]
        csound_params.orchestra = orchestra
        csound_params.score = score
        proc.set_parameters(params)

        audio_in = self.buffer_mgr.allocate('in', buffers.PyFloatAudioBlockBuffer())
        ctrl = self.buffer_mgr.allocate('ctrl', buffers.PyFloatControlValueBuffer())
        self.buffer_mgr.allocate('ev', buffers.PyAtomDataBuffer())
        audio_out = self.buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())

        # clear all buffers
        forge = lv2.AtomForge(self.urid_mapper)
        forge.set_buffer(self.buffer_mgr.data('ev'), 10240)
        with forge.sequence():
            pass
        ctrl[0] = 0.0
        for i in range(self.host_system.block_size):
            audio_in[i] = 0.0
            audio_out[i] = 0.0

        proc.connect_port(self.ctxt, 0, self.buffer_mgr.data('in'))
        proc.connect_port(self.ctxt, 1, self.buffer_mgr.data('out'))
        proc.connect_port(self.ctxt, 2, self.buffer_mgr.data('ctrl'))
        proc.connect_port(self.ctxt, 3, self.buffer_mgr.data('ev'))

        return proc

    def test_synth(self):
        orchestra = textwrap.dedent('''\
            0dbfs = 1.0
            ksmps = 32
            nchnls = 2

            gaIn chnexport "in", 1
            gaOut chnexport "out", 2
            gkCtrl chnexport "ctrl", 1

            instr 1
              gaOut = 1.0
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
        audio_out = self.buffer_mgr['out']
        self.assertTrue(all(v == 0.0 for v in audio_out[:32]))
        self.assertTrue(all(v == 1.0 for v in audio_out[32:64]))
        self.assertTrue(all(v == 0.0 for v in audio_out[64:]))

    def test_filter(self):
        orchestra = textwrap.dedent('''\
            0dbfs = 1.0
            ksmps = 32
            nchnls = 2

            gaIn chnexport "in", 1
            gaOut chnexport "out", 2
            gkCtrl chnexport "ctrl", 1

            instr 1
              gaOut = gkCtrl * gaIn
            endin
            ''')
        score = textwrap.dedent('''\
            i1 0 -1
            e 10000
            ''')
        proc = self.create_proc(orchestra, score)

        audio_in = self.buffer_mgr['in']
        for i in range(self.host_system.block_size):
            audio_in[i] = 1.0
            audio_in[i] = 1.0
        self.buffer_mgr['ctrl'][0] = 0.5

        proc.process_block(self.ctxt, None)  # TODO: pass time_mapper

        # The instrument only gets active with one cycle delay, so the first 32 samples a silence.
        audio_out = self.buffer_mgr['out']
        self.assertTrue(all(v == 0.0 for v in audio_out[:32]))
        self.assertTrue(all(v == 0.5 for v in audio_out[32:]))

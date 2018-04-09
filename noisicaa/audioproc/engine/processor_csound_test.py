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

# TODO: mypy-unclean

import textwrap

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisidev import unittest_engine_utils
from noisicaa.bindings.lv2 import atom
from noisicaa.bindings.lv2 import urid
from noisicaa import node_db
from . import block_context
from . import buffers
from . import processor


class ProcessorCsoundTestMixin(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.TestCase):
    def test_csound(self):
        node_description = node_db.NodeDescription(
            type=node_db.NodeDescription.PROCESSOR,
            ports=[
                node_db.PortDescription(
                    name='gain',
                    direction=node_db.PortDescription.INPUT,
                    type=node_db.PortDescription.KRATE_CONTROL,
                ),
                node_db.PortDescription(
                    name='in',
                    direction=node_db.PortDescription.INPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
                node_db.PortDescription(
                    name='out',
                    direction=node_db.PortDescription.OUTPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
            ],
            processor=node_db.ProcessorDescription(
                type=node_db.ProcessorDescription.CSOUND,
            ),
            csound=node_db.CSoundDescription(
                orchestra=textwrap.dedent("""\
                    sr=44100
                    0dbfs=1
                    ksmps=32
                    nchnls=1

                    gkGain chnexport "gain", 1
                    gaIn chnexport "in", 1
                    gaOut chnexport "out", 2

                    instr 1
                      gaOut = gkGain * gaIn
                    endin
                """),
                score='i1 0 -1',
            ),
        )

        proc = processor.PyProcessor('test_node', self.host_system, node_description)
        proc.setup()

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        gain = buffer_mgr.allocate('gain', buffers.PyFloatControlValueBuffer())
        audio_in = buffer_mgr.allocate('in', buffers.PyFloatAudioBlockBuffer())
        audio_out = buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('gain'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('in'))
        proc.connect_port(ctxt, 2, buffer_mgr.data('out'))

        for i in range(self.host_system.block_size):
            audio_in[i] = 1.0
            audio_out[i] = 0.0
        gain[0] = 0.5

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(all(v == 0.5 for v in audio_out))

        proc.cleanup()

    def test_event_input_port(self):
        node_description = node_db.NodeDescription(
            type=node_db.NodeDescription.PROCESSOR,
            ports=[
                node_db.PortDescription(
                    name='in',
                    direction=node_db.PortDescription.INPUT,
                    type=node_db.PortDescription.EVENTS,
                ),
                node_db.PortDescription(
                    name='out',
                    direction=node_db.PortDescription.OUTPUT,
                    type=node_db.PortDescription.AUDIO,
                ),
            ],
            processor=node_db.ProcessorDescription(
                type=node_db.ProcessorDescription.CSOUND,
            ),
            csound=node_db.CSoundDescription(
                orchestra=textwrap.dedent("""\
                    sr=44100
                    0dbfs=1
                    ksmps=32
                    nchnls=1

                    gaOut chnexport "out", 2

                    instr 1
                      iPitch = p4
                      iVelocity = p5

                      iFreq = cpsmidinn(iPitch)
                      iVolume = -20 * log10(127^2 / iVelocity^2)

                      gaOut = db(iVolume) * linseg(0, 0.08, 1, 0.1, 0.6, 0.5, 0.0) * poscil(1.0, iFreq)
                    endin
                """),
                score='',
            ),
        )

        proc = processor.PyProcessor('test_node', self.host_system, node_description)
        proc.setup()

        buffer_mgr = unittest_engine_utils.BufferManager(self.host_system)

        buffer_mgr.allocate('in', buffers.PyAtomDataBuffer())
        audio_out = buffer_mgr.allocate('out', buffers.PyFloatAudioBlockBuffer())

        ctxt = block_context.PyBlockContext()
        ctxt.sample_pos = 1024

        proc.connect_port(ctxt, 0, buffer_mgr.data('in'))
        proc.connect_port(ctxt, 1, buffer_mgr.data('out'))

        forge = atom.AtomForge(urid.static_mapper)
        forge.set_buffer(buffer_mgr.data('in'), 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        for i in range(self.host_system.block_size):
            audio_out[i] = 0.0

        proc.process_block(ctxt, None)  # TODO: pass time_mapper

        self.assertTrue(any(v != 0.5 for v in audio_out))

        proc.cleanup()

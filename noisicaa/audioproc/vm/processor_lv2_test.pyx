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

import sys

from libc.string cimport memset
from libc.stdint cimport uint8_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from noisidev import unittest
from noisicaa.core.status cimport *
from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 import urid
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *


cdef class TestProcessorLV2Impl(object):
    cdef PyHostData host_data
    cdef PyBlockContext ctxt
    cdef unique_ptr[Processor] processor_ptr
    cdef Processor* processor
    cdef unique_ptr[ProcessorSpec] spec_ptr
    cdef ProcessorSpec* spec

    def setup_testcase(self):
        self.host_data = PyHostData()
        self.host_data.setup()

        self.ctxt = PyBlockContext()
        self.ctxt.block_size = 128

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', self.host_data.ptr(), b'lv2')
        self.processor_ptr.reset(stor_processor.result())
        self.processor = self.processor_ptr.get()

        self.spec_ptr.reset(new ProcessorSpec())
        self.spec = self.spec_ptr.get()

    def cleanup_testcase(self):
        self.spec_ptr.reset()
        self.spec = NULL
        self.processor_ptr.reset()
        self.processor = NULL
        self.host_data.cleanup()

    def test_passthru(self):
        check(self.spec.add_port(b'gain', PortType.kRateControl, PortDirection.Input))
        check(self.spec.add_port(b'in', PortType.audio, PortDirection.Input))
        check(self.spec.add_port(b'out', PortType.audio, PortDirection.Output))
        check(self.spec.add_parameter(
            new StringParameterSpec(
                b'lv2_uri', b'http://noisicaa.odahoda.de/plugins/test-passthru')))

        check(self.processor.setup(self.spec_ptr.release()))

        cdef float audio_in[128]
        cdef float audio_out[128]
        cdef uint8_t midi_in[10240]
        cdef uint8_t midi_out[10240]

        check(self.processor.connect_port(0, <BufferPtr>audio_in))
        check(self.processor.connect_port(1, <BufferPtr>midi_in))
        check(self.processor.connect_port(2, <BufferPtr>audio_out))
        check(self.processor.connect_port(3, <BufferPtr>midi_out))

        for i in range(128):
            audio_in[i] = 1.0

        cdef atom.AtomForge forge = atom.AtomForge(urid.static_mapper)
        forge.set_buffer(midi_in, 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        memset(audio_out, 0x88, 128 * sizeof(float))

        # A blank atom with the size of the writable output buffer.
        (<atom.LV2_Atom*>midi_out).type = 0
        (<atom.LV2_Atom*>midi_out).size = 10240 - sizeof(atom.LV2_Atom)

        check(self.processor.run(self.ctxt.get(), NULL))  # TODO: pass time_mapper

        for i in range(128):
            self.assertAlmostEqual(audio_out[i], 1.0, places=2)

        seq = atom.Atom.wrap(urid.static_mapper, bytes(midi_out[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(
            [[b for b in event.atom.data[0:3]] for event in seq.events],
            [[0x90, 60, 100], [0x80, 60, 0]])

        self.processor.cleanup()


class TestProcessorLV2(TestProcessorLV2Impl, unittest.TestCase):
    pass

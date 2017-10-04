# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from libc.stdint cimport uint8_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 import urid
from noisicaa.core.status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *

import textwrap
import unittest
import sys


class TestProcessorCSound(unittest.TestCase):
    def test_csound(self):
        cdef Status status

        cdef PyHostData host_data = PyHostData()
        host_data.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.ptr(), b'csound')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())

        cdef Processor* processor = processor_ptr.get()

        orchestra = textwrap.dedent('''\
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
        ''').encode('utf-8')

        score = b'i1 0 -1'

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
        spec.get().add_port(b'in', PortType.audio, PortDirection.Input)
        spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'csound_orchestra', orchestra))
        spec.get().add_parameter(new StringParameterSpec(b'csound_score', score))

        check(processor.setup(spec.release()))

        cdef float gain
        cdef float inbuf[128]
        cdef float outbuf[128]

        processor.connect_port(0, <BufferPtr>&gain)
        processor.connect_port(1, <BufferPtr>inbuf)
        processor.connect_port(2, <BufferPtr>outbuf)

        gain = 0.5
        for i in range(128):
            inbuf[i] = 1.0
        for i in range(128):
            outbuf[i] = 0.0

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 128

        check(processor.run(ctxt.get()))

        for i in range(128):
            self.assertEqual(outbuf[i], 0.5)

        processor.cleanup()

    def test_event_input_port(self):
        cdef Status status

        cdef PyHostData host_data = PyHostData()
        host_data.setup()

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.ptr(), b'csound')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())

        cdef Processor* processor = processor_ptr.get()

        orchestra = textwrap.dedent('''\
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
        ''').encode('utf-8')

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'in', PortType.atomData, PortDirection.Input)
        spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'csound_orchestra', orchestra))
        spec.get().add_parameter(new StringParameterSpec(b'csound_score', b''))

        check(processor.setup(spec.release()))

        cdef uint8_t inbuf[10240]
        cdef float outbuf[128]

        processor.connect_port(0, <BufferPtr>inbuf)
        processor.connect_port(1, <BufferPtr>outbuf)

        cdef atom.AtomForge forge = atom.AtomForge(urid.static_mapper)
        forge.set_buffer(inbuf, 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        for i in range(128):
            outbuf[i] = 0.0

        cdef PyBlockContext ctxt = PyBlockContext()
        ctxt.block_size = 128

        check(processor.run(ctxt.get()))

        self.assertTrue(any(outbuf[i] != 0.0 for i in range(128)))

        processor.cleanup()

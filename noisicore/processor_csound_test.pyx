from libcpp.string cimport string
from libcpp.memory cimport unique_ptr
from .status cimport *
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

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(Processor.create(host_data.get(), b'csound'))
        self.assertTrue(processor_ptr.get() != NULL)

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

        status = processor.setup(spec.release())
        self.assertFalse(status.is_error(), status.message())

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

        cdef BlockContext ctxt
        ctxt.block_size = 128

        processor.run(&ctxt)

        for i in range(128):
            self.assertEqual(outbuf[i], 0.5)

        processor.cleanup()

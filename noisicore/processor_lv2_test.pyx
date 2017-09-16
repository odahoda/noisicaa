from libcpp.string cimport string
from libcpp.memory cimport unique_ptr
from .status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *

import unittest
import sys


class TestProcessorLV2(unittest.TestCase):
    def test_lv2(self):
        cdef Status status

        cdef PyHostData host_data = PyHostData()
        host_data.setup();

        cdef StatusOr[Processor*] stor_processor = Processor.create(host_data.ptr(), b'lv2')
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())

        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
        spec.get().add_port(b'in', PortType.audio, PortDirection.Input)
        spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'lv2_uri', b'http://lv2plug.in/plugins/eg-amp'))

        check(processor.setup(spec.release()))

        cdef float gain
        cdef float inbuf[128]
        cdef float outbuf[128]

        processor.connect_port(0, <BufferPtr>&gain)
        processor.connect_port(1, <BufferPtr>inbuf)
        processor.connect_port(2, <BufferPtr>outbuf)

        gain = -6
        for i in range(128):
            inbuf[i] = 1.0
        for i in range(128):
            outbuf[i] = 0.0

        cdef BlockContext ctxt
        ctxt.block_size = 128

        check(processor.run(&ctxt))

        for i in range(128):
            self.assertAlmostEqual(outbuf[i], 0.5, places=2)

        processor.cleanup()

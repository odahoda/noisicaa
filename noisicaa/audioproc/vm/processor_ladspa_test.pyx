from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

import unittest
import sys

from noisicaa.core.status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *
from .processor_spec cimport *
from .host_data cimport *


class TestProcessorLadspa(unittest.TestCase):
    def test_ladspa(self):
        cdef Status status

        cdef unique_ptr[HostData] host_data
        host_data.reset(new HostData())

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            b'test_node', host_data.get(), b'ladspa')
        check(stor_processor)
        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(stor_processor.result())
        cdef Processor* processor = processor_ptr.get()

        cdef unique_ptr[ProcessorSpec] spec
        spec.reset(new ProcessorSpec())
        spec.get().add_port(b'gain', PortType.kRateControl, PortDirection.Input)
        spec.get().add_port(b'in', PortType.audio, PortDirection.Input)
        spec.get().add_port(b'out', PortType.audio, PortDirection.Output)
        spec.get().add_parameter(new StringParameterSpec(b'ladspa_library_path', b'/usr/lib/ladspa/amp.so'))
        spec.get().add_parameter(new StringParameterSpec(b'ladspa_plugin_label', b'amp_mono'))

        check(processor.setup(spec.release()))

        cdef float gain
        cdef float inbuf[128]
        cdef float outbuf[128]

        check(processor.connect_port(0, <BufferPtr>&gain))
        check(processor.connect_port(1, <BufferPtr>inbuf))
        check(processor.connect_port(2, <BufferPtr>outbuf))

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

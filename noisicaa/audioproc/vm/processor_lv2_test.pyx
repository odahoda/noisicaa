from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

import unittest
import sys

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

    def setUp(self):
        self.host_data = PyHostData()
        self.host_data.setup()

        self.ctxt = PyBlockContext()
        self.ctxt.block_size = 128

        cdef StatusOr[Processor*] stor_processor = Processor.create(
            self.host_data.ptr(), b'lv2')
        self.processor_ptr.reset(stor_processor.result())
        self.processor = self.processor_ptr.get()

        self.spec_ptr.reset(new ProcessorSpec())
        self.spec = self.spec_ptr.get()

    def tearDown(self):
        self.spec_ptr.reset()
        self.spec = NULL
        self.processor_ptr.reset()
        self.processor = NULL
        self.host_data.cleanup()

    def test_amp(self):
        check(self.spec.add_port(b'gain', PortType.kRateControl, PortDirection.Input))
        check(self.spec.add_port(b'in', PortType.audio, PortDirection.Input))
        check(self.spec.add_port(b'out', PortType.audio, PortDirection.Output))
        check(self.spec.add_parameter(
            new StringParameterSpec(b'lv2_uri', b'http://lv2plug.in/plugins/eg-amp')))

        check(self.processor.setup(self.spec_ptr.release()))

        cdef float gain
        cdef float inbuf[128]
        cdef float outbuf[128]

        check(self.processor.connect_port(0, <BufferPtr>&gain))
        check(self.processor.connect_port(1, <BufferPtr>inbuf))
        check(self.processor.connect_port(2, <BufferPtr>outbuf))

        gain = -6
        for i in range(128):
            inbuf[i] = 1.0
        for i in range(128):
            outbuf[i] = 0.0

        check(self.processor.run(self.ctxt.get()))

        for i in range(128):
            self.assertAlmostEqual(outbuf[i], 0.5, places=2)

        self.processor.cleanup()

    def test_fifths(self):
        # This one requires the urid map feature.
        check(self.spec.add_port(b'in', PortType.atomData, PortDirection.Input))
        check(self.spec.add_port(b'out', PortType.atomData, PortDirection.Output))
        check(self.spec.add_parameter(
            new StringParameterSpec(b'lv2_uri', b'http://lv2plug.in/plugins/eg-fifths')))

        check(self.processor.setup(self.spec_ptr.release()))

        cdef uint8_t inbuf[10240]
        cdef uint8_t outbuf[10240]

        check(self.processor.connect_port(0, <BufferPtr>inbuf))
        check(self.processor.connect_port(1, <BufferPtr>outbuf))

        cdef atom.AtomForge forge = atom.AtomForge(urid.static_mapper)
        forge.set_buffer(inbuf, 10240)
        with forge.sequence():
            forge.write_midi_event(0, bytes([0x90, 60, 100]), 3)
            forge.write_midi_event(64, bytes([0x80, 60, 0]), 3)

        check(self.processor.run(self.ctxt.get()))

        seq = atom.Atom.wrap(urid.static_mapper, bytes(outbuf[:10240]))
        self.assertIsInstance(seq, atom.Sequence)
        self.assertEqual(
            [[b for b in event.atom.data[0:3]] for event in seq.events],
            [[0x90, 60, 100], [0x90, 67, 100], [0x80, 60, 0], [0x80, 67, 0]])

        self.processor.cleanup()


class TestProcessorLV2(TestProcessorLV2Impl, unittest.TestCase):
    pass

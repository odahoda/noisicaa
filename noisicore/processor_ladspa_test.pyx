from libcpp.memory cimport unique_ptr
from .status cimport *
from .block_context cimport *
from .buffers cimport *
from .processor cimport *

import unittest
import sys

class TestProcessorLadspa(unittest.TestCase):
    def test_ladspa(self):
        cdef Status status

        cdef unique_ptr[Processor] processor_ptr
        processor_ptr.reset(Processor.create(b'ladspa'))
        self.assertTrue(processor_ptr.get() != NULL)

        cdef Processor* processor = processor_ptr.get()

        status = processor.setup()
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

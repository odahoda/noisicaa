from libc.stdint cimport uint32_t
from libcpp.string cimport string

from .status cimport *
from .buffers cimport *
from .block_context cimport *
from .processor_spec cimport *

cdef extern from "processor.h" namespace "noisicaa" nogil:
    cppclass Processor:
        @staticmethod
        Processor* create(const string& name)

        Status setup(const ProcessorSpec* spec)
        void cleanup()

        Status connect_port(uint32_t port_idx, BufferPtr buf)
        Status run(BlockContext* ctxt)


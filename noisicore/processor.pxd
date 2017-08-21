from libcpp.string cimport string

from .status cimport *
from .buffers cimport *
from .block_context cimport *

cdef extern from "processor.h" namespace "noisicaa" nogil:
    cppclass Processor:
        @staticmethod
        Processor* create(const string& name)

        Status setup()
        void cleanup()

        Status connect_port(int port_idx, BufferPtr buf)
        Status run(BlockContext* ctxt)


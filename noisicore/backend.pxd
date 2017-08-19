from libcpp.string cimport string

from .status cimport *
from .buffers cimport *

cdef extern from "backend.h" namespace "noisicaa" nogil:
    cppclass Backend:
        @staticmethod
        Backend* create(const string& name)

        Status setup()
        Status cleanup()
        Status begin_frame()
        Status end_frame()
        Status output(const string& channel, BufferPtr samples)

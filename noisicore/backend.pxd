from libc.stdint cimport uint32_t
from libcpp.string cimport string

from noisicaa.core.status cimport *
from .vm cimport *
from .buffers cimport *
from .block_context cimport *

cdef extern from "noisicore/backend.h" namespace "noisicaa" nogil:
    struct BackendSettings:
        string ipc_address
        uint32_t block_size

    cppclass Backend:
        @staticmethod
        StatusOr[Backend*] create(const string& name, const BackendSettings& settings)

        Status setup(VM* vm)
        void cleanup()
        Status begin_block(BlockContext* ctxt)
        Status end_block(BlockContext* ctxt)
        Status output(BlockContext* ctxt, const string& channel, BufferPtr samples)

        void stop()
        bool stopped() const


cdef class PyBackendSettings(object):
    cdef BackendSettings __settings

    cdef BackendSettings get(self)

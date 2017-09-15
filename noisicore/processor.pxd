from libc.stdint cimport uint32_t, uint64_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from .status cimport *
from .buffers cimport *
from .block_context cimport *
from .processor_spec cimport *
from .host_data cimport *

cdef extern from "noisicore/processor.h" namespace "noisicaa" nogil:
    cppclass Processor:
        @staticmethod
        StatusOr[Processor*] create(HostData* host_data, const string& name)

        uint64_t id() const

        Status setup(const ProcessorSpec* spec)
        void cleanup()

        StatusOr[string] get_string_parameter(const string& name)
        Status set_string_parameter(const string& name, const string& value)

        StatusOr[int64_t] get_int_parameter(const string& name)
        Status set_int_parameter(const string& name, int64_t value)

        StatusOr[float] get_float_parameter(const string& name)
        Status set_float_parameter(const string& name, float value)

        Status connect_port(uint32_t port_idx, BufferPtr buf)
        Status run(BlockContext* ctxt)


cdef class PyProcessor(object):
    cdef bytes __name
    cdef PyProcessorSpec __spec
    cdef unique_ptr[Processor] __processor_ptr
    cdef Processor* __processor

    cdef Processor* ptr(self)
    cdef Processor* release(self)

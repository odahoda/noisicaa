from libc.stdint cimport uint32_t

from .status cimport *

cdef extern from "vm.h" namespace "noisicaa" nogil:
    cppclass Processor
    cppclass Spec
    cppclass Backend
    cppclass BlockContext
    cppclass Buffer
    cppclass HostData

    cppclass VM:
        VM(HostData* host_data)

        Status setup()
        void cleanup()
        Processor* create_processor(const string& name)
        Status add_processor(Processor* processor)
        Status set_block_size(uint32_t block_size)
        Status set_spec(const Spec* spec)
        Status set_backend(Backend* backend)
        Status process_block(BlockContext* ctxt)
        Buffer* get_buffer(const string& name)

from libc.stdint cimport uint32_t

from .status cimport *
from .spec cimport *
from .buffers cimport *

cdef extern from "vm.h" namespace "noisicaa" nogil:
    cppclass VM:
        Status setup()
        void cleanup()
        Status set_block_size(uint32_t block_size)
        Status set_spec(const Spec* spec)
        Status process_block()
        Buffer* get_buffer(const string& name)

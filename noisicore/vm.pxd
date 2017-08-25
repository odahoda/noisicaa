from libc.stdint cimport uint32_t

from .status cimport *
from .spec cimport *
from .buffers cimport *
from .block_context cimport *
from .backend cimport *

cdef extern from "vm.h" namespace "noisicaa" nogil:
    cppclass VM:
        Status setup()
        void cleanup()
        Status set_block_size(uint32_t block_size)
        Status set_spec(const Spec* spec)
        Status set_backend(Backend* backend)
        Status process_block(BlockContext* ctxt)
        Buffer* get_buffer(const string& name)

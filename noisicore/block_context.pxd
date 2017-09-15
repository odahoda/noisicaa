from libc.stdint cimport uint32_t

cdef extern from "noisicore/block_context.h" namespace "noisicaa" nogil:
    struct BlockContext:
        uint32_t block_size
        uint32_t sample_pos


cdef class PyBlockContext(object):
    cdef BlockContext __ctxt

    cdef BlockContext* ptr(self)

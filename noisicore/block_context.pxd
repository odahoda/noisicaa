from libc.stdint cimport uint32_t

cdef extern from "block_context.h" namespace "noisicaa" nogil:
    struct BlockContext:
        uint32_t block_size
        uint32_t sample_pos

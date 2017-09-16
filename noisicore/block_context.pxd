from libc.stdint cimport uint32_t
from libcpp.memory cimport unique_ptr

from noisicaa.core.perf_stats cimport *

cdef extern from "noisicore/block_context.h" namespace "noisicaa" nogil:
    struct BlockContext:
        uint32_t block_size
        uint32_t sample_pos
        unique_ptr[PerfStats] perf

cdef class PyBlockContext(object):
    cdef BlockContext __ctxt
    cdef PyPerfStats __perf

    cdef BlockContext* get(self) nogil

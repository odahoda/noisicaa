from libc.stdint cimport uint32_t
from libcpp.memory cimport unique_ptr

from noisicaa.core.perf_stats cimport *
from .message_queue cimport *

cdef extern from "noisicaa/audioproc/vm/block_context.h" namespace "noisicaa" nogil:
    struct BlockContext:
        uint32_t block_size
        uint32_t sample_pos
        unique_ptr[PerfStats] perf
        unique_ptr[MessageQueue] out_messages

cdef class PyBlockContext(object):
    cdef BlockContext __ctxt
    cdef PyPerfStats __perf

    cdef BlockContext* get(self) nogil

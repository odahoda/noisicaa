from libc.stdint cimport uint32_t
from .. cimport node
from ..vm cimport buffers


cdef class WavFileSource(node.CustomNode):
    cdef object __path
    cdef object __loop
    cdef object __end_notification

    cdef object __playing

    cdef uint32_t __pos
    cdef uint32_t __num_samples
    cdef bytearray __samples_l
    cdef bytearray __samples_r

    cdef buffers.Buffer __out_left
    cdef buffers.Buffer __out_right

    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1

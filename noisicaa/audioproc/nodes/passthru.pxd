from .. cimport node
from ..vm cimport buffers

cdef class PassThru(node.CustomNode):
    cdef buffers.Buffer __in_left
    cdef buffers.Buffer __in_right
    cdef buffers.Buffer __out_left
    cdef buffers.Buffer __out_right

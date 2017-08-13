from .. cimport node
from ..vm cimport buffers

cdef class IPCNode(node.CustomNode):
    cdef object __stream

    cdef buffers.Buffer __out_l
    cdef buffers.Buffer __out_r

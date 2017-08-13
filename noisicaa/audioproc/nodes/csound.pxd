from noisicaa.bindings cimport csound
from .. cimport node

cdef class CSoundBase(node.CustomNode):
    cdef csound.CSound __csnd
    cdef object __next_csnd
    cdef dict __buffers

    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1

cdef class CSoundFilter(CSoundBase):
    cdef str __orchestra
    cdef str __score

cdef class CustomCSound(CSoundBase):
    cdef str __orchestra_preamble
    cdef str __orchestra
    cdef str __score

from noisicaa.bindings cimport ladspa
from .. cimport node

cdef class Ladspa(node.CustomNode):
    cdef object __library
    cdef object __descriptor
    cdef ladspa.Instance __instance
    cdef object __buffers

    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1

from noisicaa.bindings cimport lilv
from .. cimport node

cdef class LV2(node.CustomNode):
    cdef lilv.Plugin __plugin
    cdef lilv.Instance __instance
    cdef dict __buffers

    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1

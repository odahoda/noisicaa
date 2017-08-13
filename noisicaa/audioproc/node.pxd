
cdef class Node(object):
    cdef public object description
    cdef readonly str name
    cdef readonly str id
    cdef public object pipeline
    cdef public int broken
    cdef public dict inputs
    cdef public dict outputs
    cdef dict __parameters

cdef class CustomNode(Node):
    cdef int connect_port(self, port_name, buf) except -1
    cdef int run(self, ctxt) except -1

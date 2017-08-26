from .status cimport *

cdef extern from "host_data.h" namespace "noisicaa" nogil:
    cppclass HostData:
        Status setup()
        Status setup_lilv()

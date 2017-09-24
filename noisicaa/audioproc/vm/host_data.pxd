from libcpp.memory cimport unique_ptr
from noisicaa.core.status cimport *


cdef extern from "noisicaa/audioproc/vm/host_data.h" namespace "noisicaa" nogil:
    cppclass LV2SubSystem:
        Status setup()
        void cleanup()

    cppclass HostData:
        Status setup()
        void cleanup()

        unique_ptr[LV2SubSystem] lv2;


cdef class PyHostData(object):
    cdef unique_ptr[HostData] __host_data_ptr
    cdef HostData* __host_data

    cdef HostData* ptr(self)

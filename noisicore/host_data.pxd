from libcpp.memory cimport unique_ptr
from noisicaa.bindings.lv2.urid cimport *
from .status cimport *

cdef extern from "noisicore/host_data.h" namespace "noisicaa" nogil:
    cppclass HostData:
        Status setup()
        Status setup_lilv()
        Status setup_lv2()
        void cleanup()

        LV2_URID_Map* lv2_urid_map;
        LV2_URID_Unmap* lv2_urid_unmap;

cdef class PyHostData(object):
    cdef unique_ptr[HostData] __host_data_ptr
    cdef HostData* __host_data
    cdef URID_Mapper __mapper
    cdef URID_Map_Feature __map_feature
    cdef URID_Unmap_Feature __unmap_feature

    cdef HostData* ptr(self)

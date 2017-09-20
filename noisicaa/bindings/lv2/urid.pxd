from libc.stdint cimport uint32_t, int32_t, int64_t, uint8_t, intptr_t
from libcpp.memory cimport unique_ptr

from noisicaa.lv2 cimport urid_mapper
from .core cimport Feature


cdef extern from "lv2/lv2plug.in/ns/ext/urid/urid.h" nogil:
    ctypedef void* LV2_URID_Map_Handle
    ctypedef void* LV2_URID_Unmap_Handle

    ctypedef uint32_t LV2_URID

    cdef struct _LV2_URID_Map:
        LV2_URID_Map_Handle handle
        LV2_URID (*map)(LV2_URID_Map_Handle handle, const char* uri) except -1

    ctypedef _LV2_URID_Map LV2_URID_Map

    cdef struct _LV2_URID_Unmap:
        LV2_URID_Unmap_Handle handle
        const char* (*unmap)(LV2_URID_Unmap_Handle handle, LV2_URID urid) except <const char*>-1

    ctypedef _LV2_URID_Unmap LV2_URID_Unmap


cdef class URID_Map_Feature(Feature):
    cdef URIDMapper mapper
    cdef LV2_URID_Map data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1 with gil


cdef class URID_Unmap_Feature(Feature):
    cdef URIDMapper mapper
    cdef LV2_URID_Unmap data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1 with gil


cdef class URIDMapper(object):
    cdef unique_ptr[urid_mapper.URIDMapper] __mapper_ptr
    cdef urid_mapper.URIDMapper* __mapper

    cdef urid_mapper.URIDMapper* get(self)
    cdef urid_mapper.URIDMapper* release(self)

cdef class StaticURIDMapper(URIDMapper):
    pass

cdef class DynamicURIDMapper(URIDMapper):
    pass

cdef URIDMapper get_static_mapper()

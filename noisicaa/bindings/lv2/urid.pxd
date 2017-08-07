from libc.stdint cimport uint32_t, int32_t, int64_t, uint8_t, intptr_t

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
    cdef LV2_URID_Map data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1


cdef class URID_Unmap_Feature(Feature):
    cdef LV2_URID_Unmap data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1


cdef class URID_Mapper(object):
    cpdef LV2_URID map(self, const char* uri) except -1
    cpdef const char* unmap(self, LV2_URID urid) except <const char*>-1


cdef class URID_StaticMapper(URID_Mapper):
    cdef dict url_map
    cdef dict url_reverse_map
    cdef LV2_URID __next_urid

    cdef LV2_URID __insert(self, const char* uri) except -1

    cpdef LV2_URID map(self, const char* uri) except -1
    cpdef const char* unmap(self, LV2_URID urid) except <const char*>-1

cdef URID_Mapper get_static_mapper()


cdef class URID_DynamicMapper(URID_StaticMapper):
    cdef LV2_URID next_urid

    cpdef LV2_URID map(self, const char* uri) except -1


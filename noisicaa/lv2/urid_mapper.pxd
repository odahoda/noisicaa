from libc.stdint cimport uint32_t

cdef extern from "lv2/lv2plug.in/ns/ext/urid/urid.h" nogil:
    ctypedef uint32_t LV2_URID

cdef extern from "noisicaa/lv2/urid_mapper.h" namespace "noisicaa" nogil:
    cppclass URIDMapper:
        LV2_URID map(const char* uri)
        const char* unmap(LV2_URID urid) const

    cppclass StaticURIDMapper(URIDMapper):
        pass

    cppclass DynamicURIDMapper(URIDMapper):
        pass

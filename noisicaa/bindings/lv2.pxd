from cpython.ref cimport PyObject
from libc.stdint cimport uint32_t
from libc cimport stdlib
from libc cimport string
cimport numpy

import logging
import operator
import numpy

### DECLARATIONS ##########################################################

cdef extern from "lv2.h" nogil:
#     ctypedef void* LV2_Handle

    cdef struct _LV2_Feature:
        char* URI
        void* data

    ctypedef _LV2_Feature LV2_Feature

#     ctypedef LV2_Handle (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_instantiate_ft)(_LV2_Descriptor* descriptor, double sample_rate, char* bundle_path, LV2_Feature** features)

#     ctypedef void (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_connect_port_ft)(LV2_Handle instance, uint32_t port, void* data_location)

#     ctypedef void (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_activate_ft)(LV2_Handle instance)

#     ctypedef void (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_run_ft)(LV2_Handle instance, uint32_t sample_count)

#     ctypedef void (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_deactivate_ft)(LV2_Handle instance)

#     ctypedef void (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_cleanup_ft)(LV2_Handle instance)

#     ctypedef void* (*_LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_extension_data_ft)(char* uri)

#     cdef struct _LV2_Descriptor:
#         char* URI
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_instantiate_ft instantiate
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_connect_port_ft connect_port
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_activate_ft activate
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_run_ft run
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_deactivate_ft deactivate
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_cleanup_ft cleanup
#         _LV2_Descriptor_LV2_Descriptor__LV2_Descriptor_extension_data_ft extension_data

#     ctypedef _LV2_Descriptor LV2_Descriptor

#     LV2_Descriptor* lv2_descriptor(uint32_t index)

#     ctypedef LV2_Descriptor* (*LV2_Descriptor_Function)(uint32_t index)

#     ctypedef void* LV2_Lib_Handle

#     ctypedef void (*_LV2_Lib_Descriptor_LV2_Lib_Descriptor_cleanup_ft)(LV2_Lib_Handle handle)

#     ctypedef LV2_Descriptor* (*_LV2_Lib_Descriptor_LV2_Lib_Descriptor_get_plugin_ft)(LV2_Lib_Handle handle, uint32_t index)

#     cdef struct _LV2_Lib_Descriptor_s:
#         LV2_Lib_Handle handle
#         uint32_t size
#         _LV2_Lib_Descriptor_LV2_Lib_Descriptor_cleanup_ft cleanup
#         _LV2_Lib_Descriptor_LV2_Lib_Descriptor_get_plugin_ft get_plugin

#     ctypedef _LV2_Lib_Descriptor_s LV2_Lib_Descriptor

#     LV2_Lib_Descriptor* lv2_lib_descriptor(char* bundle_path, LV2_Feature** features)

#     ctypedef LV2_Lib_Descriptor* (*LV2_Lib_Descriptor_Function)(char* bundle_path, LV2_Feature** features)

cdef extern from "lv2/lv2plug.in/ns/ext/urid/urid.h" nogil:
    ctypedef void* LV2_URID_Map_Handle

    ctypedef void* LV2_URID_Unmap_Handle

    ctypedef uint32_t LV2_URID


    cdef struct _LV2_URID_Map:
        LV2_URID_Map_Handle handle
        LV2_URID (*map)(LV2_URID_Map_Handle handle, const char* uri)

    ctypedef _LV2_URID_Map LV2_URID_Map

    cdef struct _LV2_URID_Unmap:
        LV2_URID_Unmap_Handle handle
        const char* (*unmap)(LV2_URID_Unmap_Handle handle, LV2_URID urid)

    ctypedef _LV2_URID_Unmap LV2_URID_Unmap


cdef class Feature(object):
    cdef LV2_Feature* create_lv2_feature(self)


cdef class URID_Map_Feature(Feature):
    cdef LV2_URID_Map data

    cdef LV2_Feature* create_lv2_feature(self)


cdef class URID_Unmap_Feature(Feature):
    cdef LV2_URID_Unmap data

    cdef LV2_Feature* create_lv2_feature(self)

cdef class URID_Mapper(object):
    cdef dict url_map
    cdef dict url_reverse_map
    cdef int next_urid

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri)

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid)

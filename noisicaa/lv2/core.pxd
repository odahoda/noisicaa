# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

cdef extern from "lv2.h" nogil:
    ctypedef void* LV2_Handle

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


cdef class Feature(object):
    cdef LV2_Feature lv2_feature

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

from libc.stdint cimport uint32_t, int32_t, int64_t, uint8_t, intptr_t
from libcpp.memory cimport unique_ptr

from . cimport core
from . cimport urid_mapper


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


cdef class URID_Map_Feature(core.Feature):
    cdef urid_mapper.PyURIDMapper mapper
    cdef LV2_URID_Map data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1 with gil


cdef class URID_Unmap_Feature(core.Feature):
    cdef urid_mapper.PyURIDMapper mapper
    cdef LV2_URID_Unmap data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1 with gil

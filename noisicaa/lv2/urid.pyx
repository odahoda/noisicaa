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

from cpython.ref cimport PyObject
from libc cimport stdlib
from libc cimport string

cdef char* allocstr(str s):
    cdef char* r
    b = s.encode('utf-8')
    r = <char*>stdlib.malloc(len(b) + 1)
    string.strcpy(r, b)
    return r


cdef class URID_Map_Feature(core.Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#map'

    def __cinit__(self, urid_mapper.PyURIDMapper mapper):
        self.mapper = mapper

        self.data.handle = self.mapper.get()
        self.data.map = self.urid_map

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef LV2_URID urid_map(LV2_URID_Map_Handle handle, const char* uri) except -1 with gil:
        cdef urid_mapper.URIDMapper* mapper = <urid_mapper.URIDMapper*>handle
        return mapper.map(uri)


cdef class URID_Unmap_Feature(core.Feature):
    uri = 'http://lv2plug.in/ns/ext/urid#unmap'

    def __cinit__(self, urid_mapper.PyURIDMapper mapper):
        self.mapper = mapper

        self.data.handle = self.mapper.get()
        self.data.unmap = self.urid_unmap

        self.lv2_feature.URI = allocstr(self.uri)
        self.lv2_feature.data = &self.data

    @staticmethod
    cdef const char* urid_unmap(LV2_URID_Map_Handle handle, LV2_URID urid) except <const char*>-1 with gil:
        cdef urid_mapper.URIDMapper* mapper = <urid_mapper.URIDMapper*>handle
        return mapper.unmap(urid)

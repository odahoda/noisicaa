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

from libc.stdint cimport uint32_t
from libcpp cimport bool
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr
from libcpp.unordered_map cimport unordered_map


cdef extern from "lv2/lv2plug.in/ns/ext/urid/urid.h" nogil:
    ctypedef uint32_t LV2_URID

cdef extern from "noisicaa/lv2/urid_mapper.h" namespace "noisicaa" nogil:
    cppclass URIDMapper:
        LV2_URID map(const char* uri)
        const char* unmap(LV2_URID urid) const

    cppclass StaticURIDMapper(URIDMapper):
        pass

    cppclass DynamicURIDMapper(URIDMapper):
        bool known(const char* uri) const
        ctypedef unordered_map[string, LV2_URID].const_iterator const_iterator
        const_iterator begin() const
        const_iterator end() const

    cppclass ProxyURIDMapper(URIDMapper):
        ProxyURIDMapper(LV2_URID (*map_func)(void*, const char*), void* handle)
        void insert(const char* uri, LV2_URID urid)


cdef class PyURIDMapper(object):
    cdef URIDMapper* get(self)
    cdef URIDMapper* release(self)


cdef class PyDynamicURIDMapper(PyURIDMapper):
    cdef unique_ptr[DynamicURIDMapper] __ptr
    cdef DynamicURIDMapper* __mapper

    cdef URIDMapper* get(self)
    cdef URIDMapper* release(self)


cdef class PyProxyURIDMapper(PyURIDMapper):
    cdef unique_ptr[ProxyURIDMapper] __ptr
    cdef ProxyURIDMapper* __mapper
    cdef str __tmp_dir
    cdef str __server_address
    cdef object __quit
    cdef object __client_thread
    cdef object __client_thread_ready
    cdef object __client_thread_done
    cdef object __event_loop
    cdef object __stub
    cdef str __session_id
    cdef object __cb_server

    cdef URIDMapper* get(self)
    cdef URIDMapper* release(self)

    @staticmethod
    cdef LV2_URID map_cb(void* handle, const char* uri) with gil

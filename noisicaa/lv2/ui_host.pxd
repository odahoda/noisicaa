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

from libc.stdint cimport uint32_t
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport Status
from noisicaa.host_system cimport host_system
from noisicaa.lv2 cimport urid_mapper


cdef extern from "noisicaa/lv2/ui_host.h" namespace "noisicaa" nogil:
    cppclass LV2UIHost:
        LV2UIHost(const string&,
                  host_system.HostSystem* host_system,
                  void* handle,
                  void (*control_value_change_cb)(void*, uint32_t, float))
        Status setup()
        void cleanup()
        unsigned long int wid() const
        int width() const
        int height() const


cdef class PyLV2UIHost(object):
    cdef object __desc
    cdef host_system.PyHostSystem __host_system
    cdef object __control_value_change_cb
    cdef unique_ptr[LV2UIHost] __ptr
    cdef LV2UIHost* __host

    cdef LV2UIHost* get(self)
    cdef LV2UIHost* release(self)
    @staticmethod
    cdef void control_value_change(void* handle, uint32_t port_index, float value) with gil

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
from libcpp.memory cimport unique_ptr
from noisicaa.core.status cimport Status


cdef extern from "noisicaa/audioproc/engine/plugin_ui_host.h" namespace "noisicaa" nogil:
    cppclass PluginUIHost:
        Status setup()
        void cleanup()

        unsigned long int wid() const
        int width() const
        int height() const


cdef class PyPluginUIHost(object):
    cdef object __control_value_change_cb
    cdef unique_ptr[PluginUIHost] __plugin_ui_host_ptr
    cdef PluginUIHost* __plugin_ui_host

    cdef int init(self, PluginUIHost* plugin_ui_host) except -1
    cdef PluginUIHost* get(self) nogil
    cdef PluginUIHost* release(self) nogil
    @staticmethod
    cdef void __control_value_change(
        void* handle, uint32_t port_index, float value, uint32_t generation) with gil

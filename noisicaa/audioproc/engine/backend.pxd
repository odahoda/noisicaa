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

from noisicaa.core.status cimport Status, StatusOr
from noisicaa.host_system.host_system cimport HostSystem
from .realm cimport Realm, PyRealm
from .buffers cimport BufferPtr
from .block_context cimport BlockContext


cdef extern from "noisicaa/audioproc/engine/backend.h" namespace "noisicaa" nogil:
    struct BackendSettings:
        string datastream_address
        float time_scale

    cppclass Backend:
        @staticmethod
        StatusOr[Backend*] create(
            HostSystem* host_system, const string& name, const BackendSettings& settings)

        Status setup(Realm* realm)
        void cleanup()
        Status send_message(const string& msg)
        Status begin_block(BlockContext* ctxt)
        Status end_block(BlockContext* ctxt)
        Status output(BlockContext* ctxt, const string& channel, BufferPtr samples)


cdef class PyBackendSettings(object):
    cdef BackendSettings __settings

    cdef BackendSettings get(self)


cdef class PyBackend(object):
    cdef unique_ptr[Backend] __backend_ptr
    cdef Backend* __backend

    cdef Backend* get(self) nogil

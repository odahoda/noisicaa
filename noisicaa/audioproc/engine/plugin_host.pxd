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

from noisicaa.core.status cimport Status, StatusOr
from noisicaa.host_system.host_system cimport HostSystem
from noisicaa.audioproc.engine.buffers cimport BufferPtr
from .plugin_ui_host cimport PluginUIHost

cdef extern from "limits.h" nogil:
    cpdef enum:
        PATH_MAX

cdef extern from "pthread.h" nogil:
    ctypedef int pthread_cond_t
    ctypedef int pthread_mutex_t

cdef extern from "noisicaa/audioproc/engine/plugin_host.h" namespace "noisicaa" nogil:
    cppclass PluginMemoryMapping:
        char shmem_path[PATH_MAX]
        size_t cond_offset
        uint32_t block_size
        uint32_t num_buffers

        cppclass Buffer:
            uint32_t port_index
            size_t offset

    cppclass PluginCond:
        uint32_t magic
        bool set
        pthread_mutex_t mutex
        pthread_cond_t cond

    cppclass PluginHost:
        @staticmethod
        StatusOr[PluginHost*] create(const string& spec_serialized, HostSystem* host_system)

        # uint64_t id() const
        const string& node_id() const
        StatusOr[PluginUIHost*] create_ui(
            void* handle,
            void (*control_value_change_cb)(void*, uint32_t, float, uint32_t))

        Status setup()
        void cleanup()

        Status main_loop(int pipe_fd)
        void exit_loop()

        # Status handle_message(const string& msg)

        Status connect_port(uint32_t port_idx, BufferPtr buf)
        Status process_block(uint32_t block_size)
        bool has_state()
        StatusOr[string] get_state()
        Status set_state(const string& serialized_state)


cdef class PyPluginHost(object):
    cdef unique_ptr[PluginHost] __plugin_host_ptr
    cdef PluginHost* __plugin_host

    cdef PluginHost* get(self) nogil
    cdef PluginHost* release(self) nogil

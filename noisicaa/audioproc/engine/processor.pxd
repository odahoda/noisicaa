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

from libc.stdint cimport uint8_t, uint32_t, uint64_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport Status, StatusOr
from noisicaa.core.refcount cimport RefCounted
from noisicaa.host_system.host_system cimport HostSystem
from noisicaa.audioproc.public.time_mapper cimport TimeMapper
from noisicaa.audioproc.public.musical_time cimport MusicalTime
from .buffers cimport Buffer
from .block_context cimport BlockContext


cdef extern from "noisicaa/audioproc/engine/processor.h" namespace "noisicaa" nogil:
    enum ProcessorState:
        INACTIVE
        SETUP
        RUNNING
        BROKEN
        CLEANUP

    cppclass Processor(RefCounted):
        @staticmethod
        StatusOr[Processor*] create(
            const string& realm_name, const string& node_id, HostSystem* host_system,
            const string& desc_serialized)

        uint64_t id() const
        const string& node_id() const
        ProcessorState state() const

        Status setup()

        Status handle_message(const string& msg)
        Status set_parameters(const string& msg)
        Status set_description(const string& msg)

        void connect_port(BlockContext* ctxt, uint32_t port_idx, Buffer* buf)
        void process_block(BlockContext* ctxt, TimeMapper* time_mapper)


cdef class PyProcessor(object):
    cdef object __desc
    cdef Processor* __processor

    cdef Processor* get(self) nogil

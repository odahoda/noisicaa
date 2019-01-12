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

from libc.stdint cimport uint32_t, uint64_t
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport Status, StatusOr
from noisicaa.core.refcount cimport RefCounted
from noisicaa.host_system.host_system cimport HostSystem, PyHostSystem
from .block_context cimport BlockContext
from .control_value cimport ControlValue
from .processor cimport Processor, ProcessorState
from .player cimport Player
from .spec cimport Spec
from .buffers cimport Buffer


cdef extern from "noisicaa/audioproc/engine/realm.h" namespace "noisicaa" nogil:
    cppclass Program:
        pass

    cppclass Realm(RefCounted):
        Realm(const string& name, HostSystem* host_system, Player* player)

        const string& name()

        Status setup()
        void cleanup()
        void clear_programs()
        void set_notification_callback(
            void (*callback)(void*, const string&), void* userdata);
        Status add_processor(Processor* processor)
        Status add_control_value(ControlValue* cv)
        Status add_child_realm(Realm* cv)
        StatusOr[Realm*] get_child_realm(const string& name)
        Status set_float_control_value(const string& name, float value, uint32_t generation)
        Status send_processor_message(uint64_t processor_id, const string& msg_serialized)
        Status set_spec(const Spec* spec)
        StatusOr[Program*] get_active_program()
        Status process_block(Program* program)
        Status run_maintenance()
        Buffer* get_buffer(const string& name)
        BlockContext* block_context()


cdef class PyProgram(object):
    cdef Program* __program

    cdef void set(self, Program* program) nogil
    cdef Program* get(self) nogil


cdef class PyRealm(object):
    cdef Realm* __realm
    cdef PyHostSystem __host_system
    cdef dict __dict__

    cdef Realm* get(self) nogil

    @staticmethod
    cdef void __notification_callback(
        void* c_self, const string& notification_serialized) with gil

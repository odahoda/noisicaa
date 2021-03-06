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
from libcpp.vector cimport vector
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport Status, StatusOr
from noisicaa.audioproc.public.musical_time cimport MusicalDuration
from .buffers cimport BufferType
from .control_value cimport ControlValue
from .opcodes cimport OpCode, OpArg
from .processor cimport Processor
from .realm cimport Realm


cdef extern from "noisicaa/audioproc/engine/spec.h" namespace "noisicaa" nogil:
    cppclass Spec:
        void set_bpm(uint32_t bpm)
        uint32_t bpm() const

        void set_duration(MusicalDuration duration)
        MusicalDuration duration() const

        Status append_opcode(OpCode opcode, const vector[OpArg]& args)
        int num_ops() const
        OpCode get_opcode(int idx) const
        const OpArg& get_oparg(int idx, int arg) const

        Status append_buffer(const string& name, BufferType* type)
        int num_buffers() const
        const BufferType* get_buffer(int idx) const
        StatusOr[int] get_buffer_idx(const char* name) const

        Status append_control_value(ControlValue* cv)
        int num_control_values() const
        ControlValue* get_control_value(int idx) const
        StatusOr[int] get_control_value_idx(const ControlValue* cv) const

        Status append_processor(Processor* processor)
        int num_processors() const
        Processor* get_processor(int idx) const
        StatusOr[int] get_processor_idx(const Processor* processor) const

        Status append_child_realm(Realm* child_realm)
        int num_child_realm() const
        Realm* get_child_realm(int idx) const
        StatusOr[int] get_child_realm_idx(const Realm* child_realm) const


cdef class PySpec(object):
    cdef unique_ptr[Spec] __spec_ptr
    cdef Spec* __spec

    cdef Spec* get(self) nogil
    cdef Spec* release(self) nogil

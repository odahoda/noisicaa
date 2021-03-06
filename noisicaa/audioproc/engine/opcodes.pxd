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

from libcpp.string cimport string
from libcpp.vector cimport vector
from libc.stdint cimport int64_t

from noisicaa.core.status cimport Status


cdef extern from "noisicaa/audioproc/engine/opcodes.h" namespace "noisicaa" nogil:
    enum OpCode:
        NOOP
        END
        CALL_CHILD_REALM
        COPY
        CLEAR
        MIX
        MUL
        SET_FLOAT
        FETCH_CONTROL_VALUE
        FETCH_CONTROL_VALUE_TO_AUDIO
        POST_RMS
        NOISE
        SINE
        MIDI_MONKEY,
        CONNECT_PORT
        CALL
        LOG_RMS
        LOG_ATOM
        NUM_OPCODES

    enum OpArgType:
        INT
        FLOAT
        STRING

    cppclass OpArg:
        OpArg(int64_t value)
        OpArg(float value)
        OpArg(const string& value)
        OpArgType type()
        int64_t int_value() const
        float float_value() const
        const string& string_value() const

    struct ProgramState
    ctypedef Status (*OpFunc)(ProgramState*, const vector[OpArg]& args)

    struct OpSpec:
        OpCode opcode
        const char* name
        const char* argspec
        OpFunc init
        OpFunc run

    cdef OpSpec opspecs[]

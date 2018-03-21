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

from libc.stdint cimport int64_t
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

cdef extern from "noisicaa/audioproc/engine/control_value.h" namespace "noisicaa" nogil:
    enum ControlValueType:
        FloatCV
        IntCV

    cppclass ControlValue:
        ControlValueType type() const
        const string& name() const

    cppclass FloatControlValue(ControlValue):
        FloatControlValue(const string& name, float value)

        float value() const
        void set_value(float value)

    cppclass IntControlValue(ControlValue):
        IntControlValue(const string& name, int64_t value)

        int64_t value() const
        void set_value(int64_t value)


cdef class PyControlValue(object):
    cdef unique_ptr[ControlValue] __cv_ptr
    cdef ControlValue* __cv

    cdef ControlValue* get(self) nogil
    cdef ControlValue* release(self) nogil

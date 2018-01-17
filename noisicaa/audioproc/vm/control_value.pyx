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

import enum

class PyControlValueType(enum.Enum):
    Float = ControlValueType.FloatCV
    Int = ControlValueType.IntCV


cdef class PyControlValue(object):
    cdef ControlValue* ptr(self):
        return self.__cv

    cdef ControlValue* release(self):
        return self.__cv_ptr.release()

    @property
    def name(self):
        return bytes(self.__cv.name()).decode('utf-8')


cdef class PyFloatControlValue(PyControlValue):
    def __init__(self, name, value):
        self.__cv_ptr.reset(new FloatControlValue(name.encode('utf-8'), value))
        self.__cv = self.__cv_ptr.get()

    @property
    def value(self):
        cdef FloatControlValue* cv = <FloatControlValue*>self.__cv;
        return float(cv.value())

    @value.setter
    def value(self, v):
        cdef FloatControlValue* cv = <FloatControlValue*>self.__cv;
        cv.set_value(<float>v)


cdef class PyIntControlValue(PyControlValue):
    def __init__(self, name, value):
        self.__cv_ptr.reset(new IntControlValue(name.encode('utf-8'), value))
        self.__cv = self.__cv_ptr.get()

    @property
    def value(self):
        cdef IntControlValue* cv = <IntControlValue*>self.__cv;
        return int(cv.value())

    @value.setter
    def value(self, v):
        cdef IntControlValue* cv = <IntControlValue*>self.__cv;
        cv.set_value(<int64_t>v)


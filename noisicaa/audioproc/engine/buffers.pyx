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

from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem


cdef class PyBufferType(object):
    cdef BufferType* get(self) nogil:
        return self.__type

    cdef BufferType* release(self) nogil:
        return self.__type_ref.release()

    @property
    def view_type(self):
        raise NotImplementedError


cdef class PyFloatControlValueBuffer(PyBufferType):
    def __init__(self):
        self.__type_ref.reset(new FloatControlValueBuffer())
        self.__type = self.__type_ref.get()

    def __str__(self):
        return 'FloatControlValueBuffer'

    @property
    def view_type(self):
        return 'f'


cdef class PyFloatAudioBlockBuffer(PyBufferType):
    def __init__(self, type):
        self.__type_ref.reset(new FloatAudioBlockBuffer(type))
        self.__type = self.__type_ref.get()

    def __str__(self):
        return 'FloatAudioBlockBuffer'

    @property
    def view_type(self):
        return 'f'


cdef class PyAtomDataBuffer(PyBufferType):
    def __init__(self):
        self.__type_ref.reset(new AtomDataBuffer())
        self.__type = self.__type_ref.get()

    def __str__(self):
        return 'AtomDataBuffer'

    @property
    def view_type(self):
        return 'b'


cdef class PyPluginCondBuffer(PyBufferType):
    def __init__(self):
        self.__type_ref.reset(new PluginCondBuffer())
        self.__type = self.__type_ref.get()

    def __str__(self):
        return 'PluginCondBuffer'

    @property
    def view_type(self):
        return 'B'

    def set_cond(self, uint8_t[:] buf):
        cdef PluginCondBuffer* c_type = <PluginCondBuffer*>self.__type
        cdef BufferPtr c_buf = <BufferPtr>&buf[0]
        with nogil:
            check(c_type.set_cond(c_buf))

    def clear_cond(self, uint8_t[:] buf):
        cdef PluginCondBuffer* c_type = <PluginCondBuffer*>self.__type
        cdef BufferPtr c_buf = <BufferPtr>&buf[0]
        with nogil:
            check(c_type.clear_cond(c_buf))

    def wait_cond(self, uint8_t[:] buf):
        cdef PluginCondBuffer* c_type = <PluginCondBuffer*>self.__type
        cdef BufferPtr c_buf = <BufferPtr>&buf[0]
        with nogil:
            check(c_type.wait_cond(c_buf))


cdef class PyBuffer(object):
    def __init__(self, PyHostSystem host_system, PyBufferType buf_type, uint8_t[:] buf):
        self.__type = buf_type

        self.__buffer_ref.reset(new Buffer(host_system.get(), self.__type.get(), <BufferPtr>&buf[0]))
        self.__buffer = self.__buffer_ref.get()

    cdef Buffer* get(self) nogil:
        return self.__buffer

    cdef Buffer* release(self) nogil:
        return self.__buffer_ref.release()

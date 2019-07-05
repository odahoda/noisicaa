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

from libc.stdint cimport uint8_t, uint32_t
from libcpp.string cimport string
from libcpp.map cimport map
from libcpp.memory cimport unique_ptr

from noisicaa import node_db
from noisicaa.core.status cimport check
from noisicaa.host_system.host_system cimport PyHostSystem
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine cimport buffers
from noisicaa.audioproc.engine.buffer_arena cimport PyBufferArena, BufferArena


cdef class BufferManager(object):
    cdef PyHostSystem __host_system
    cdef BufferArena* __arena
    cdef bytearray __array
    cdef size_t __size
    cdef buffers.BufferPtr __buffer
    cdef uint32_t __offset
    cdef map[string, unique_ptr[buffers.Buffer]] __buffers
    cdef dict __views

    def __init__(self, PyHostSystem host_system, PyBufferArena arena=None, size=2**20):
        self.__host_system = host_system

        if arena is not None:
            self.__array = None
            self.__arena = arena.get()
            self.__size = self.__arena.size()
            self.__buffer = self.__arena.address()
        else:
            self.__arena = NULL
            self.__array = bytearray(size)
            self.__size = size
            self.__buffer = self.__array

        self.__offset = 0
        self.__views = {}

    def allocate_from_node_description(self, node_description, prefix=''):
        for port in node_description.ports:
            btype = {
                node_db.PortDescription.AUDIO: buffers.PyFloatAudioBlockBuffer,
                node_db.PortDescription.ARATE_CONTROL: buffers.PyFloatAudioBlockBuffer,
                node_db.PortDescription.KRATE_CONTROL: buffers.PyFloatControlValueBuffer,
                node_db.PortDescription.EVENTS: buffers.PyAtomDataBuffer,
            }[port.type]
            self.allocate(prefix + port.name, btype())

    def connect_ports(self, proc, ctxt, node_description, prefix=''):
        for idx, port in enumerate(node_description.ports):
            proc.connect_port(ctxt, idx, self.data(prefix + port.name))

    def allocate(self, str name, buffers.PyBufferType btype):
        cdef string c_name = name.encode('utf-8')
        assert self.__buffers.count(c_name) == 0, name

        cdef uint32_t size = btype.get().size(self.__host_system.get())
        assert(self.__offset + size <= self.__size)
        cdef buffers.BufferPtr data = self.__buffer + self.__offset

        cdef unique_ptr[buffers.Buffer] buf
        buf.reset(new buffers.Buffer(self.__host_system.get(), btype.release(), data))
        self.__offset += size

        check(buf.get().setup())

        self.__buffers[c_name] = unique_ptr[buffers.Buffer](buf.release())
        view = <uint8_t[:size]>data
        self.__views[name] = (btype, view, memoryview(view).cast(btype.view_type))

        return self.__views[name][2]

    def __getitem__(self, name):
        return self.__views[name][2]

    def type(self, name):
        return self.__views[name][0]

    def data(self, name):
        return self.__views[name][1]

    cdef buffers.BufferPtr get_buffer(self, str name) except *:
        cdef string c_name = name.encode('utf-8')
        assert self.__buffers.count(c_name) == 1, name
        return self.__buffers[c_name].get().data()

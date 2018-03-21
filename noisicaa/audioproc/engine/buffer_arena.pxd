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

from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport Status
from noisicaa.core.logging cimport Logger
from .buffers cimport BufferPtr


cdef extern from "noisicaa/audioproc/engine/buffer_arena.h" namespace "noisicaa" nogil:
    cppclass BufferArena:
        BufferArena(size_t size, Logger* logger)
        Status setup()
        const string& name() const
        size_t size() const
        BufferPtr address() const


cdef class PyBufferArena(object):
    cdef unique_ptr[BufferArena] __arena_ptr
    cdef BufferArena* __arena

    cdef BufferArena* get(self) nogil

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
from libc.stdint cimport uint8_t, uint32_t

from noisicaa.bindings.lv2 cimport urid
from noisicaa.core.status cimport *

from .host_data cimport *

cdef extern from "noisicaa/audioproc/vm/buffers.h" namespace "noisicaa" nogil:
    ctypedef uint8_t* BufferPtr

    cppclass BufferType:
        pass

    cppclass Float(BufferType):
        pass

    cppclass FloatAudioBlock(BufferType):
        pass

    cppclass AtomData(BufferType):
        pass

    cppclass Buffer:
        Buffer(HostData* host_data, BufferType* type)

        const BufferType* type() const
        BufferPtr data()
        uint32_t size() const

        Status allocate(uint32_t block_size)

        Status clear()
        Status mix(const Buffer* other)
        Status mul(float factor)


cdef class PyBufferType(object):
    cdef unique_ptr[BufferType] cpptype

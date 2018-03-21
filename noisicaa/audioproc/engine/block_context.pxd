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

from libc.stdint cimport uint32_t
from libcpp.memory cimport unique_ptr
from libcpp.vector cimport vector

from noisicaa.core.perf_stats cimport PyPerfStats, PerfStats
from noisicaa.audioproc.public.musical_time cimport MusicalTime
from .message_queue cimport MessageQueue
from .buffer_arena cimport BufferArena


cdef extern from "noisicaa/audioproc/engine/block_context.h" namespace "noisicaa" nogil:
    struct SampleTime:
        MusicalTime start_time
        MusicalTime end_time

    cppclass BlockContext:
        uint32_t sample_pos
        vector[SampleTime] time_map
        unique_ptr[PerfStats] perf
        unique_ptr[MessageQueue] out_messages
        BufferArena* buffer_arena


cdef class PyBlockContext(object):
    cdef unique_ptr[BlockContext] __ptr
    cdef BlockContext* __ctxt
    cdef PyPerfStats __perf

    @staticmethod
    cdef PyBlockContext create(BlockContext*)
    cdef BlockContext* get(self) nogil

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

from noisicaa.core.perf_stats cimport *
from .musical_time cimport *
from .message_queue cimport *

cdef extern from "noisicaa/audioproc/vm/block_context.h" namespace "noisicaa" nogil:
    struct SampleTime:
        MusicalTime start_time
        MusicalTime end_time

    struct BlockContext:
        uint32_t block_size
        uint32_t sample_pos
        vector[SampleTime] time_map
        unique_ptr[PerfStats] perf
        unique_ptr[MessageQueue] out_messages

cdef class PyBlockContext(object):
    cdef BlockContext __ctxt
    cdef PyPerfStats __perf

    cdef BlockContext* get(self) nogil

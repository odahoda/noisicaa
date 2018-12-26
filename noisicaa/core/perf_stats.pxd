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

from cpython.ref cimport PyObject
from libc.stdint cimport uint64_t
from libcpp.functional cimport function
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

cdef extern from "noisicaa/core/perf_stats.h" namespace "noisicaa" nogil:
    cppclass PerfStats:
        struct Span:
            uint64_t id
            char name[128]
            uint64_t parent_id
            uint64_t start_time_nsec
            uint64_t end_time_nsec

        ctypedef function[uint64_t] clock_func_t

        PerfStats()
        PerfStats(clock_func_t clock)

        void reset()
        void start_span(const char* name, uint64_t parent_id)
        void start_span(const char* name)
        void end_span()
        void append_span(const Span& span)
        uint64_t current_span_id() const
        int num_spans() const
        Span span(int idx) const

        size_t serialized_size() const
        void serialize_to(char* buf) const
        void deserialize(const string& data)


cdef class PyPerfStats(object):
    cdef unique_ptr[PerfStats] __stats_ptr
    cdef PerfStats* __stats
    cdef object __clock

    @staticmethod
    cdef PyPerfStats create(PerfStats*)

    cdef PerfStats* get(self)
    cdef PerfStats* release(self)

    @staticmethod
    cdef uint64_t __clock_cb(PyObject* s) with gil

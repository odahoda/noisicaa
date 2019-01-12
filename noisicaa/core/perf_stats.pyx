#!/usr/bin/python3

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

from libc.string cimport strncpy

import contextlib
import random
import threading
import time


cdef extern from "<functional>" namespace "std" nogil:
    # Ugly hack, because cython does not support variadic templates.
    cdef PerfStats.clock_func_t bind(uint64_t (PyObject*), PyObject*) except +


class Span(object):
    def __init__(self):
        self.id = None
        self.name = None
        self.parent_id = None
        self.start_time_nsec = None
        self.end_time_nsec = None

    @property
    def duration(self):
        if (self.start_time_nsec is not None
            and self.end_time_nsec is not None):
            return self.end_time_nsec - self.start_time_nsec
        return None

    def __str__(self):
        return '<%s %016x(%016x) %s %s %s>' % (
            self.name, self.id, self.parent_id,
            self.start_time_nsec, self.end_time_nsec, self.duration)
    __repr__ = __str__


cdef class PyPerfStats(object):
    def __init__(self, clock=None):
        self.__clock = clock
        if clock is not None:
            self.__stats_ptr.reset(
                new PerfStats(bind(PyPerfStats.__clock_cb, <PyObject*>self)))
        else:
            self.__stats_ptr.reset(new PerfStats())

        self.__stats = self.__stats_ptr.get()

    @staticmethod
    cdef PyPerfStats create(PerfStats* c_stats):
        if c_stats == NULL:
            return None

        cdef PyPerfStats stats = PyPerfStats.__new__(PyPerfStats)
        stats.__stats = c_stats
        return stats

    cdef PerfStats* get(self):
        return self.__stats_ptr.get()

    cdef PerfStats* release(self):
        return self.__stats_ptr.release()

    @staticmethod
    cdef uint64_t __clock_cb(PyObject* s) with gil:
        cdef PyPerfStats self = <object>s
        return self.__clock()

    def __len__(self):
        return int(self.__stats.num_spans())

    def __iter__(self):
        cdef PerfStats.Span span
        for idx in range(self.__stats.num_spans()):
            span = self.__stats.span(idx)
            s = Span()
            s.id = int(span.id)
            s.name = bytes(span.name).decode('utf-8')
            s.parent_id = int(span.parent_id)
            s.start_time_nsec = int(span.start_time_nsec)
            s.end_time_nsec = int(span.end_time_nsec)
            yield s

    @property
    def current_span_id(self):
        return int(self.__stats.current_span_id())

    @property
    def spans(self):
        return list(self)

    def reset(self):
        self.__stats.reset()

    def serialize(self):
        buf = bytearray(self.__stats.serialized_size())
        self.__stats.serialize_to(buf)
        return bytes(buf)

    def deserialize(self, bytes data):
        self.__stats.reset()
        self.__stats.deserialize(data)

    def start_span(self, name, parent_id=None):
        name = name.encode('utf-8')
        if parent_id is not None:
            self.__stats.start_span(name, parent_id)
        else:
            self.__stats.start_span(name)

    def end_span(self):
        self.__stats.end_span()

    @contextlib.contextmanager
    def track(self, name, parent_id=None):
        self.start_span(name, parent_id)
        try:
            yield
        finally:
            self.end_span()

    def add_spans(self, msg):
        cdef PerfStats.Span span
        for s in msg.spans:
            span.id = s.id
            strncpy(span.name, s.name.encode('utf-8'), 128)
            if s.parent_id == 0:
                span.parent_id = self.current_span_id
            else:
                span.parent_id = s.parent_id
            span.start_time_nsec = s.start_time_nsec
            span.end_time_nsec = s.end_time_nsec
            self.__stats.append_span(span)

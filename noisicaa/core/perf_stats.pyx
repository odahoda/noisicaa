#!/usr/bin/python3

from cpython.ref cimport PyObject
from libc.string cimport strncpy

import contextlib
import random
import threading
import time

import capnp

from . import perf_stats_capnp


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
                new PerfStats(<PerfStats.clock_func_t>PyPerfStats.__clock_cb, <PyObject*>self))
        else:
            self.__stats_ptr.reset(new PerfStats())

        self.__stats = self.__stats_ptr.get()

    cdef PerfStats* get(self):
        return self.__stats_ptr.get()

    cdef PerfStats* release(self):
        return self.__stats_ptr.release()

    @staticmethod
    cdef uint64_t __clock_cb(void* data) with gil:
        cdef PyPerfStats self = <object>data
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
        msg = perf_stats_capnp.PerfStats.new_message()
        msg.init('spans', len(self))
        for idx, span in enumerate(self):
            s = msg.spans[idx]
            s.id = span.id
            s.name = span.name
            s.parentId = span.parent_id
            s.startTimeNSec = span.start_time_nsec
            s.endTimeNSec = span.end_time_nsec
        return msg

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
            if s.parentId == 0:
                span.parent_id = self.current_span_id
            else:
                span.parent_id = s.parentId
            span.start_time_nsec = s.startTimeNSec
            span.end_time_nsec = s.endTimeNSec
            self.__stats.append_span(span)

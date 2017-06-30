#!/usr/bin/python3

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


class PerfStats(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._spans = []
        self._stacks = threading.local()

    def serialize(self):
        msg = perf_stats_capnp.PerfStats.new_message()
        with self._lock:
            msg.init('spans', len(self._spans))
            for idx, span in enumerate(self._spans):
                s = msg.spans[idx]
                s.id = span.id
                s.name = span.name
                s.parentId = span.parent_id
                s.startTimeNSec = span.start_time_nsec
                s.endTimeNSec = span.end_time_nsec
        return msg

    def get_time_nsec(self):  # pragma: no coverage
        return int(time.perf_counter() * 1e9)

    def get_stack(self):
        try:
            return self._stacks.local_stack
        except AttributeError:
            self._stacks.local_stack = []
            return self._stacks.local_stack

    @property
    def current_span_id(self):
        stack = self.get_stack()
        return stack[-1].id if stack else 0

    def start_span(self, name, parent_id=None):
        stack = self.get_stack()
        if parent_id is None:
            parent_id = stack[-1].id if stack else 0
        span = Span()
        span.id = random.getrandbits(64)
        span.name = name
        span.parent_id = parent_id
        span.start_time_nsec = self.get_time_nsec()
        stack.append(span)
        with self._lock:
            self._spans.append(span)

    def end_span(self):
        stack = self.get_stack()
        span = stack.pop(-1)
        span.end_time_nsec = self.get_time_nsec()

    @contextlib.contextmanager
    def track(self, name, parent_id=None):
        self.start_span(name, parent_id)
        try:
            yield
        finally:
            self.end_span()

    def add_spans(self, msg):
        with self._lock:
            for s in msg.spans:
                span = Span()
                span.id = s.id
                span.name = s.name
                if s.parentId == 0:
                    span.parent_id = self.current_span_id
                else:
                    span.parent_id = s.parentId
                span.start_time_nsec = s.startTimeNSec
                span.end_time_nsec = s.endTimeNSec
                self._spans.append(span)

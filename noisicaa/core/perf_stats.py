#!/usr/bin/python3

import contextlib
import random
import threading
import time


class Span(object):
    def __init__(self, name, parent_id):
        self.id = random.getrandbits(64)
        self.name = name
        self.parent_id = parent_id
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


class PerfStats(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._spans = []
        self._stacks = threading.local()

    def get_spans(self):
        with self._lock:
            return self._spans[:]

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
        span = Span(name, parent_id)
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

    def add_spans(self, spans):
        with self._lock:
            for span in spans:
                if span.parent_id is 0:
                    span.parent_id = self.current_span_id
                self._spans.append(span)


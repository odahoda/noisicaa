#!/usr/bin/python3

import logging

import intervaltree

logger = logging.getLogger(__name__)


class NoteEvent(object):
    def __init__(self, begin, end, pitch, velocity):
        self.begin = begin
        self.end = end
        self.pitch = pitch
        self.velocity = velocity

    def __hash__(self):
        return hash((self.begin, self.end, self.pitch, self.velocity))

    def __str__(self):
        return '<NoteEvent begin=%s end=%s pitch=%s velocity=%s>' % (
            self.begin, self.end, self.pitch, self.velocity)
    __repr__ = __str__

    def __eq__(self, other):
        return (
            self.begin == other.begin
            and self.end == other.end
            and self.pitch == other.pitch
            and self.velocity == other.velocity)

    def __lt__(self, other):
        return (
            (self.begin, self.end, self.pitch, self.velocity)
            < (other.begin, other.end, other.pitch, other.velocity))


class EventSet(object):
    def __init__(self):
        self.__intervals = intervaltree.IntervalTree()
        self.__events = {}

    def get_intervals(self, begin, end):
        for interval in self.__intervals[begin:end]:
            yield interval.data

    def get_intervals_at(self, t):
        for interval in self.__intervals[t]:
            yield interval.data

    def add(self, event):
        interval = intervaltree.Interval(event.begin, event.end, event)
        self.__intervals.add(interval)
        self.__events[event] = interval

    def remove(self, event):
        interval = self.__events.pop(event)
        self.__intervals.remove(interval)

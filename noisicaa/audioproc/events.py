#!/usr/bin/python3

import logging

logger = logging.getLogger(__name__)


class Event(object):
    def __init__(self, sample_pos, tags=None):
        super().__init__()
        self.sample_pos = sample_pos
        self.tags = set()
        if tags is not None:
            self.tags |= tags

    def __lt__(self, other):
        return self.sample_pos < other.sample_pos


class EmptyEvent(Event):
    pass


class NoteEvent(Event):
    def __init__(self, sample_pos, note, tags=None):
        super().__init__(sample_pos, tags)
        self.note = note

    def __str__(self):
        return "%s(%d, %s)" % (self.__class__.__name__, self.sample_pos, self.note)


class NoteOnEvent(NoteEvent):
    def __init__(self, sample_pos, note, volume=127, tags=None):
        super().__init__(sample_pos, note, tags)
        self.volume = volume

    def __str__(self):
        return "%s(%d, %s %s)" % (self.__class__.__name__, self.sample_pos, self.note, self.volume)


class NoteOffEvent(NoteEvent):
    def __init__(self, sample_pos, note, tags=None):
        super().__init__(sample_pos, note)


class EndOfStreamEvent(Event):
    def __init__(self, sample_pos, tags=None):
        super().__init__(sample_pos, tags)

#!/usr/bin/python3

import logging

logger = logging.getLogger(__name__)


class Event(object):
    def __init__(self, timepos, tags=None):
        super().__init__()
        self.timepos = timepos
        self.tags = set()
        if tags is not None:
            self.tags |= tags


class EmptyEvent(Event):
    pass


class NoteEvent(Event):
    def __init__(self, timepos, note, tags=None):
        super().__init__(timepos, tags)
        self.note = note

    def __str__(self):
        return "%s(%d, %s)" % (self.__class__.__name__, self.timepos, self.note)


class NoteOnEvent(NoteEvent):
    def __init__(self, timepos, note, volume=127, tags=None):
        super().__init__(timepos, note, tags)
        self.volume = volume


class NoteOffEvent(NoteEvent):
    def __init__(self, timepos, note, tags=None):
        super().__init__(timepos, note)


class EndOfStreamEvent(Event):
    def __init__(self, timepos, tags=None):
        super().__init__(timepos, tags)

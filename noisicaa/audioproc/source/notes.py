#!/usr/bin/python3

import logging

from ..ports import EventOutputPort
from ..node import Node

logger = logging.getLogger(__name__)

class NoteSource(Node):
    def __init__(self, track):
        super().__init__()

        self._output = EventOutputPort('out')
        self.add_output(self._output)

        self._track = track
        self._timepos = None
        self._event_source = None

    def start(self):
        super().start()
        self._timepos = 0
        self._event_source = self._track.create_event_source()

    def run(self):
        for event in self._event_source.get_events(
                self._timepos, self._timepos + 4096):
            assert self._timepos <= event.timepos < self._timepos + 4096
            self._output.add_event(event)
        self._timepos += 4096


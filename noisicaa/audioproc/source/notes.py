#!/usr/bin/python3

import logging

from ..ports import EventOutputPort
from ..node import Node
from ..events import EndOfStreamEvent
from ..exceptions import EndOfStreamError

logger = logging.getLogger(__name__)

class NoteSource(Node):
    def __init__(self, track):
        super().__init__()

        self._output = EventOutputPort('out')
        self.add_output(self._output)

        self._track = track
        self._end_of_stream = None
        self._event_source = None

    def setup(self):
        super().setup()
        self._end_of_stream = False
        self._event_source = self._track.create_event_source()

    def run(self, timepos):
        if self._end_of_stream:
            raise EndOfStreamError

        for event in self._event_source.get_events(
                timepos, timepos + 4096):
            assert timepos <= event.timepos < timepos + 4096

            self._output.add_event(event)

            if isinstance(event, EndOfStreamEvent):
                self._end_of_stream = True
                break


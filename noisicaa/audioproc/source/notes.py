#!/usr/bin/python3

import logging

from ..ports import EventOutputPort
from ..node import Node
from ..events import EndOfStreamEvent

logger = logging.getLogger(__name__)

class NoteSource(Node):
    def __init__(self, track):
        super().__init__()

        self._output = EventOutputPort('out')
        self.add_output(self._output)

        self._track = track
        self._end_of_stream = None
        self._event_source = None

    async def setup(self):
        await super().setup()
        self._end_of_stream = False
        self._event_source = self._track.create_event_source()

    def run(self, timepos):
        for event in self._event_source.get_events(
                timepos, timepos + 4096):
            assert timepos <= event.timepos < timepos + 4096

            self._output.add_event(event)


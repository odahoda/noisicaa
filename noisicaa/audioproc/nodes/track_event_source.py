#!/usr/bin/python3

import logging
import random

from noisicaa import music
from .. import ports
from .. import node
from .. import node_types
from .. import events

logger = logging.getLogger(__name__)

class TrackEventSource(node.Node):
    desc = node_types.NodeType()
    desc.name = 'track_event_source'
    desc.port('out', 'output', 'events')

    def __init__(self, event_loop, name=None, id=None):
        super().__init__(event_loop, name, id)

        self._output = ports.EventOutputPort('out')
        self.add_output(self._output)

    def run(self, timepos):
        self._output.events.clear()

        # TODO: real events from a connected track.
        if random.random() < 0.05:
            self._output.events.append(
                events.NoteOnEvent(timepos, music.Pitch.from_midi(random.randint(40, 90))))


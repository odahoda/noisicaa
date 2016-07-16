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
    desc.parameter('queue_name', 'string')

    def __init__(self, event_loop, name=None, id=None, queue_name=None):
        super().__init__(event_loop, name, id)

        self.queue_name = queue_name

        self._output = ports.EventOutputPort('out')
        self.add_output(self._output)

    def run(self, ctxt):
        self._output.events.clear()
        self._output.events.extend(
            self.pipeline.backend.get_events(self.queue_name))

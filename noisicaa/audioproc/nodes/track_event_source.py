#!/usr/bin/python3

import logging
import random

from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from .. import events

logger = logging.getLogger(__name__)

class TrackEventSource(node.CustomNode):
    class_name = 'track_event_source'

    def __init__(self, event_loop, name=None, id=None, queue_name=None):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.EventPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description, name, id)

        self.queue_name = queue_name

    def run(self, ctxt):
        output_port = self.outputs['out']
        output_port.events.clear()
        output_port.events.extend(
            self.pipeline.backend.get_events(self.queue_name))

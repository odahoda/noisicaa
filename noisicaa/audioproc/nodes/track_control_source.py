#!/usr/bin/python3

import logging
import random

import numpy

from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from .. import events

logger = logging.getLogger(__name__)

class TrackControlSource(node.CustomNode):
    class_name = 'track_control_source'

    def __init__(self, *, entity_name, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.ControlPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.entity_name = entity_name

    def run(self, ctxt):
        output_port = self.outputs['out']

        output_port.frame.resize(ctxt.duration)

        entity = ctxt.entities.get(self.entity_name, None)
        if entity is not None:
            output_port.frame[0:len(entity.frame)] = entity.frame
        else:
            output_port.frame.fill(0.0)

#!/usr/bin/python3

import logging
import random

import numpy

from noisicaa import music
from .. import ports
from .. import node
from .. import node_types
from .. import events

logger = logging.getLogger(__name__)

class TrackControlSource(node.Node):
    desc = node_types.NodeType()
    desc.name = 'track_control_source'
    desc.port('out', 'output', 'control')
    desc.parameter('entity_name', 'string')

    def __init__(self, event_loop, name=None, id=None, entity_name=None):
        super().__init__(event_loop, name, id)

        self.entity_name = entity_name

        self._output = ports.ControlOutputPort('out')
        self.add_output(self._output)

    def run(self, ctxt):
        self._output.frame.resize(ctxt.duration)

        entity = ctxt.in_frame.entities.get(self.entity_name, None)
        if entity is not None:
            numpy.copyto(self._output.frame, entity.frame)
        else:
            self._output.frame.fill(0.0)

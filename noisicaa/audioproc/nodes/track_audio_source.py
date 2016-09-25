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

class TrackAudioSource(node.Node):
    class_name = 'track_audio_source'

    def __init__(self, event_loop, name=None, id=None, entity_name=None):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output,
                    channels='stereo'),
            ])

        super().__init__(event_loop, description, name, id)

        self.entity_name = entity_name

    def run(self, ctxt):
        output_port = self.outputs['out']

        output_port.frame.resize(ctxt.duration)

        entity = ctxt.in_frame.entities.get(self.entity_name, None)
        if entity is not None:
            output_port.frame.copy_from(entity.frame)
        else:
            output_port.frame.clear()

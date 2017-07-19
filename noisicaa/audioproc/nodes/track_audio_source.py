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

class TrackAudioSource(node.CustomNode):
    class_name = 'track_audio_source'

    def __init__(self, *, entity_name, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.entity_name = entity_name

        self.__left = None
        self.__right = None

    def connect_port(self, port_name, buf):
        if port_name == 'left':
            self.__left = buf
        elif port_name == 'right':
            self.__right = buf
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        entity = ctxt.entities.get(self.entity_name, None)
        if entity is not None:
            assert len(entity.frame.shape) == 2
            assert entity.frame.shape[0] == ctxt.duration
            assert entity.frame.shape[1] == 2

            bytes_l = entity.frame[:,0].tobytes()
            bytes_r = entity.frame[:,1].tobytes()

            self.__left[0:len(buf_l)] = bytes_l
            self.__right[0:len(buf_r)] = bytes_r

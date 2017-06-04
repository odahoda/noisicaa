#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import ports
from .. import node
from .. import audio_format

logger = logging.getLogger(__name__)


class PassThru(node.CustomNode):
    class_name = 'passthru'

    def __init__(self, event_loop, name='passthru', id=None):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description, name, id)

        self.__in_left = None
        self.__in_right = None
        self.__out_left = None
        self.__out_right = None

    def connect_port(self, port_name, buf):
        if port_name == 'in:left':
            self.__in_left = buf
        elif port_name == 'in:right':
            self.__in_right = buf
        elif port_name == 'out:left':
            self.__out_left = buf
        elif port_name == 'out:right':
            self.__out_right = buf
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        length = 4 * ctxt.duration
        self.__out_left[0:length] = self.__in_left[0:length]
        self.__out_right[0:length] = self.__in_right[0:length]

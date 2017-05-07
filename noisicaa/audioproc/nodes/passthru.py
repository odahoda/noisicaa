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
                    name='in',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description, name, id)

        self.__in = None
        self.__out = None

    def connect_port(self, port_name, buf, offset):
        if port_name == 'in':
            self.__in = (buf, offset)
        elif port_name == 'out':
            self.__out = (buf, offset)
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        length = 4 * ctxt.duration
        buf_in, offset_in = self.__in
        buf_out, offset_out = self.__out
        buf_out[offset_out:offset_out+length] = buf_in[offset_in:offset_in+length]

#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)

class TrackControlSource(node.BuiltinNode):
    class_name = 'track_control_source'

    def __init__(self, *, track_id, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.ARateControlPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.track_id = track_id

        self.__buf = None

    def connect_port(self, port_name, buf):
        if port_name == 'out':
            self.__buf = buf
        else:
            raise ValueError(port_name)

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id,
            self.outputs['out'].buf_name))
        return seq

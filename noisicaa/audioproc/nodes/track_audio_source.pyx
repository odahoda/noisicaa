#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)

class TrackAudioSource(node.BuiltinNode):
    class_name = 'track_audio_source'

    def __init__(self, *, track_id, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.track_id = track_id

        self.__left = None
        self.__right = None

    def connect_port(self, port_name, buf):
        if port_name == 'out:left':
            self.__left = buf
        elif port_name == 'out:right':
            self.__right = buf
        else:
            raise ValueError(port_name)

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id + ':left',
            self.outputs['out:left'].buf_name))
        seq.add(ast.FetchBuffer(
            'track:' + self.track_id + ':right',
            self.outputs['out:right'].buf_name))

        return seq

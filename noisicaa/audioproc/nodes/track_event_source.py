#!/usr/bin/python3

import logging
import random

from noisicaa import core
from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from ..vm import ast
from ..vm import buffer_type

logger = logging.getLogger(__name__)


class TrackEventSource(node.BuiltinNode):
    class_name = 'track_event_source'

    def __init__(self, *, track_id, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.EventPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.track_id = track_id

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.FetchEntity(
            'track:' + self.track_id,
            self.outputs['out'].buf_name))
        seq.add(ast.AllocBuffer(
            self.id + ':messages', buffer_type.AtomData(10240)))
        seq.add(ast.FetchMessages(
            core.build_labelset({core.MessageKey.trackId: self.track_id}),
            self.id + ':messages'))
        seq.add(ast.MixBuffers(
            self.id + ':messages', self.outputs['out'].buf_name))

        return seq

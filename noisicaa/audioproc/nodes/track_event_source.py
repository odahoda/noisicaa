#!/usr/bin/python3

import logging
import random

from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from .. import events
from ..vm import ast

logger = logging.getLogger(__name__)

class TrackEventSource(node.BuiltinNode):
    class_name = 'track_event_source'

    def __init__(self, event_loop, name=None, id=None, entity_id=None):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.EventPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description, name, id)

        self.entity_id = entity_id

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.FetchEntity(
            self.entity_id,
            self.outputs['out'].buf_name))
        return seq

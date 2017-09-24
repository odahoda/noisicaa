#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node

logger = logging.getLogger(__name__)


class Sink(node.BuiltinNode):
    class_name = 'sink'

    def __init__(self, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
            ])

        super().__init__(description=description, id='sink', **kwargs)

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_opcode('OUTPUT', self.inputs['in:left'].buf_name, 'left')
        spec.append_opcode('OUTPUT', self.inputs['in:right'].buf_name, 'right')

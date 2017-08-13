#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)


class Sink(node.BuiltinNode):
    class_name = 'sink'

    def __init__(self):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
            ])

        super().__init__(description=description, id='sink')

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.Output(
            self.inputs['in:left'].buf_name,
            'left'))
        seq.add(ast.Output(
            self.inputs['in:right'].buf_name,
            'right'))
        return seq
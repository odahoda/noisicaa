#!/usr/bin/python3

import logging

from noisicaa import node_db

from .. import node
from ..vm import ast

logger = logging.getLogger(__name__)


class Sink(node.BuiltinNode):
    class_name = 'sink'

    def __init__(self, event_loop):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='audio_left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='audio_right',
                    direction=node_db.PortDirection.Input),
            ])

        super().__init__(event_loop, description, id='sink')

    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        seq.add(ast.OutputStereo())
        return seq

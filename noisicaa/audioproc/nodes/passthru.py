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

    def run(self, ctxt):
        input_port = self.inputs['in']
        output_port = self.outputs['out']
        output_port.frame.resize(ctxt.duration)
        output_port.frame.copy_from(input_port.frame)

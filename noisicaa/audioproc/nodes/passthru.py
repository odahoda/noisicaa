#!/usr/bin/python3

import logging

from .. import ports
from .. import node
from .. import node_types

logger = logging.getLogger(__name__)


class PassThru(node.Node):
    desc = node_types.NodeType()
    desc.name = 'passthru'
    desc.port('in', 'input', 'audio')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, description=None, name='passthru', id=None):
        super().__init__(event_loop, name, id)

        self._input = ports.AudioInputPort('in')
        self.add_input(self._input)

        self._output = ports.AudioOutputPort('out')
        self.add_output(self._output)

    def run(self, ctxt):
        self._output.frame.resize(ctxt.duration)
        self._output.frame.copy_from(self._input.frame)

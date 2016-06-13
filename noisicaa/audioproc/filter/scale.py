#!/usr/bin/python3

import logging

from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node
from ..node_types import NodeType

logger = logging.getLogger(__name__)


class Scale(Node):
    desc = NodeType()
    desc.name = 'scale'
    desc.port('in', 'input', 'audio')
    desc.port('out', 'output', 'audio')
    desc.parameter('factor', 'float')

    def __init__(self, factor):
        super().__init__('scale(%.2f)' % factor)

        self._input = AudioInputPort('in')
        self.add_input(self._input)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._factor = factor

    def run(self, timepos):
        self._input.frame.mul(self._factor)
        self._output.frame.copy_from(self._input.frame)

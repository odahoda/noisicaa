#!/usr/bin/python3

import logging

from ..ports import AudioOutputPort
from ..node import Node
from ..node_types import NodeType

logger = logging.getLogger(__name__)


class SilenceSource(Node):
    desc = NodeType()
    desc.name = 'silence'
    desc.port('out', 'output', 'audio')

    def __init__(self):
        super().__init__()

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

    def run(self, timepos):
        self._output.frame.clear()


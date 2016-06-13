#!/usr/bin/python3

import logging
import time

from ..ports import AudioInputPort
from ..node import Node
from ..node_types import NodeType

logger = logging.getLogger(__name__)


class NullSink(Node):
    desc = NodeType()
    desc.name = 'nullsink'
    desc.port('in', 'input', 'audio')

    def __init__(self):
        super().__init__()

        self._input = AudioInputPort('in')
        self.add_input(self._input)

    def run(self, timepos):
        pass

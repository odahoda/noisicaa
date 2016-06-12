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
    desc.parameter('sleep', 'float')

    def __init__(self, sleep=0):
        super().__init__()

        self._sleep = sleep
        self._input = AudioInputPort('in')
        self.add_input(self._input)

    def run(self):
        # Sinks don't use run(), but I have to define this, to make pylint
        # happy.
        raise RuntimeError

    def consume(self, framesize=4096):
        self._input.get_frame(framesize)
        if self._sleep > 0:
            time.sleep(self._sleep)

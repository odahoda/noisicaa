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

        self._timepos = 0

    def start(self):
        super().start()
        self._timepos = 0

    def run(self):
        frame = self._output.create_frame(self._timepos)
        frame.resize(4096)
        self._timepos += len(frame)

        logger.debug('Node %s created %s', self.name, frame)
        self._output.add_frame(frame)

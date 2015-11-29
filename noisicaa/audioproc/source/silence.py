#!/usr/bin/python3

import logging

from ..ports import AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class SilenceSource(Node):
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

        logger.info('Node %s created %s', self.name, frame)
        self._output.add_frame(frame)

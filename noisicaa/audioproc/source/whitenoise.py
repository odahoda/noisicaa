#!/usr/bin/python3

import logging
import random

from ..ports import AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class WhiteNoiseSource(Node):
    def __init__(self, name=None):
        super().__init__(name)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._timepos = 0

    def start(self):
        super().start()
        self._timepos = 0

    def run(self):
        frame = self._output.create_frame(self._timepos)
        frame.resize(4096)
        samples = frame.samples
        # pylint thinks that frame.audio_format is a class object.
        num_channels = frame.audio_format.num_channels  # pylint: disable=E1101
        for ch in range(num_channels):
            ch_samples = samples[ch]
            for i in range(len(frame)):
                ch_samples[i] = random.uniform(-1.0, 1.0)
        self._timepos += len(frame)

        logger.info('Node %s created %s', self.name, frame)
        self._output.add_frame(frame)

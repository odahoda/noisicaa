#!/usr/bin/python3

import logging

from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class Scale(Node):
    def __init__(self, factor):
        super().__init__('scale(%.2f)' % factor)

        self._input = AudioInputPort('in')
        self.add_input(self._input)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._factor = factor

    def run(self):
        frame = self._input.get_frame(4096)
        samples = frame.samples
        for ch in range(frame.audio_format.num_channels):
            ch_samples = samples[ch]
            for i in range(len(frame)):
                ch_samples[i] *= self._factor
        self._output.add_frame(frame)

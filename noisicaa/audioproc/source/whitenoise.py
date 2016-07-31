#!/usr/bin/python3

import logging
import random

from ..ports import AudioOutputPort
from ..node import Node
from ..node_types import NodeType

logger = logging.getLogger(__name__)


class WhiteNoiseSource(Node):
    desc = NodeType()
    desc.name = 'whitenoise'
    desc.port('out', 'output', 'audio')

    def __init__(self, name=None):
        super().__init__(name)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

    def run(self, ctxt):
        samples = self._output.frame.samples
        # pylint thinks that frame.audio_format is a class object.
        num_channels = self._output.frame.audio_format.num_channels  # pylint: disable=E1101
        for ch in range(num_channels):
            ch_samples = samples[ch]
            for i in range(len(self._output.frame)):
                ch_samples[i] = random.uniform(-0.2, 0.2)

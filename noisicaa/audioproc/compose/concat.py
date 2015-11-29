#!/usr/bin/python3

import logging

from ..exceptions import EndOfStreamError
from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class Concat(Node):
    def __init__(self):
        super().__init__()

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._timepos = 0
        self._inputs = []
        self._current_input = 0

    def append_input(self, port):
        p = AudioInputPort('in-%d' % (len(self.inputs) + 1))
        self.add_input(p)
        p.connect(port)
        self._inputs.append(p)

    def run(self):
        while True:
            if self._current_input >= len(self._inputs):
                raise EndOfStreamError

            try:
                frame = self._inputs[self._current_input].get_frame(4096)
            except EndOfStreamError:
                self._current_input += 1
            else:
                self._timepos += len(frame)
                self._output.add_frame(frame)
                break

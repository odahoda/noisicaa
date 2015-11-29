#!/usr/bin/python3

import logging
from ..exceptions import EndOfStreamError
from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class TimeSlice(Node):
    def __init__(self, duration):
        super().__init__('timeslice(%d)' % duration)

        self._input = AudioInputPort('in')
        self.add_input(self._input)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._duration = duration
        self._timepos = 0

    def start(self):
        super().start()
        self._timepos = 0

    def run(self):
        if self._timepos >= self._duration:
            raise EndOfStreamError

        frame = self._input.get_frame(min(self._duration - self._timepos, 4096))
        self._output.add_frame(frame)
        self._timepos += len(frame)

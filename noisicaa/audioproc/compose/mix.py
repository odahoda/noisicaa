#!/usr/bin/python3

import logging
import pprint

from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node

logger = logging.getLogger(__name__)


class Mix(Node):
    _next_port = 1

    def __init__(self, name=None):
        super().__init__(name)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._timepos = 0
        self._inputs = []

    def append_input(self, port):
        with self.pipeline.writer_lock():
            num = self._next_port
            self._next_port += 1
        p = AudioInputPort('in-%d' % num)
        self.add_input(p)
        p.connect(port)
        self._inputs.append(p)
        return p

    def remove_input(self, port_name):
        try:
            port = self.inputs[port_name]
        except KeyError:
            logger.error(
                "%s not found in %s", port_name, pprint.pformat(self.inputs))
            raise

        port.disconnect()
        del self.inputs[port.name]
        self._inputs.remove(port)

    def run(self):
        out_frame = self._output.create_frame(self._timepos)
        out_frame.resize(4096)
        for input in self._inputs:  # pylint: disable=W0622
            frame = input.get_frame(len(out_frame))
            if len(frame) < len(out_frame):
                out_frame.resize(len(frame))
            out_frame.add(frame)

        self._timepos += len(out_frame)
        self._output.add_frame(out_frame)

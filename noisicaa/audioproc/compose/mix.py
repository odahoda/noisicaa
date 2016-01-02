#!/usr/bin/python3

import logging
import pprint

from noisicaa.core import callbacks
from ..ports import AudioInputPort, AudioOutputPort
from ..node import Node
from ..exceptions import EndOfStreamError

logger = logging.getLogger(__name__)


class Mix(Node):
    _next_port = 1

    def __init__(self, name=None, stop_on_end_of_stream=False):
        super().__init__(name)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._timepos = 0
        self._stop_on_end_of_stream = stop_on_end_of_stream
        self._inputs = []

        self.listeners = callbacks.CallbackRegistry()

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
            try:
                frame = input.get_frame(len(out_frame))
            except EndOfStreamError:
                if self._stop_on_end_of_stream:
                    self.stop()
                    self.listeners.call('stop')
                    break
                else:
                    raise

            if len(frame) < len(out_frame):
                out_frame.resize(len(frame))
            out_frame.add(frame)

        self._timepos += len(out_frame)
        self._output.add_frame(out_frame)

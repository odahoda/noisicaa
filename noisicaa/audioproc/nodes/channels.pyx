#!/usr/bin/python3

import logging

from .. import ports
from .. cimport node
from .. import audio_format

logger = logging.getLogger(__name__)


cdef class SplitChannels(node.CustomNode):
    class_name = 'split_channels'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._input = ports.AudioInputPort('in', audio_format.CHANNELS_STEREO)
        self.add_input(self._input)

        self._left = ports.AudioOutputPort('left', audio_format.CHANNELS_MONO)
        self.add_output(self._left)

        self._right = ports.AudioOutputPort('right', audio_format.CHANNELS_MONO)
        self.add_output(self._right)

    cdef int run(self, ctxt) except -1:
        self._left.frame.resize(ctxt.duration)
        self._right.frame.resize(ctxt.duration)

        self._left.frame.samples[0] = self._input.frame.samples[0]
        self._right.frame.samples[0] = self._input.frame.samples[1]

        return 0


cdef class JoinChannels(node.CustomNode):
    class_name = 'join_channels'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._left = ports.AudioInputPort('left', audio_format.CHANNELS_MONO)
        self.add_input(self._left)

        self._right = ports.AudioInputPort('right', audio_format.CHANNELS_MONO)
        self.add_input(self._right)

        self._output = ports.AudioOutputPort('out', audio_format.CHANNELS_STEREO)
        self.add_output(self._output)

    cdef int run(self, ctxt) except -1:
        assert len(self._left.frame) == ctxt.duration
        assert len(self._right.frame) == ctxt.duration

        self._output.frame.resize(ctxt.duration)

        self._output.frame.samples[0] = self._left.frame.samples[0]
        self._output.frame.samples[1] = self._right.frame.samples[0]

        return 0

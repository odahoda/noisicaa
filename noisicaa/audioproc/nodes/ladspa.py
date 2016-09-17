#!/usr/bin/python3

import logging

from .. import ports
from .. import node
from .. import node_types
from .. import audio_format

logger = logging.getLogger(__name__)


class Ladspa(node.Node):
    desc = node_types.NodeType()
    desc.name = 'ladspa'
    desc.port('in', 'input', 'audio')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, description=None, name='ladspa', id=None):
        super().__init__(event_loop, name, id)

        self._input = ports.AudioInputPort('in', audio_format.CHANNELS_MONO)
        self.add_input(self._input)

        self._output = ports.AudioOutputPort('out', audio_format.CHANNELS_MONO)
        self.add_output(self._output)

    def set_param(self, **kwargs):
        pass

    def run(self, ctxt):
        self._output.frame.resize(ctxt.duration)
        self._output.frame.copy_from(self._input.frame)

#!/usr/bin/python3

import asyncio
import logging
import os
import pickle
import random
import threading

from noisicaa.core import ipc
from noisicaa import music

from .. import ports
from .. import node
from .. import frame
from .. import node_types
from .. import events
from .. import audio_stream
from .. import data
from .. import audio_format

logger = logging.getLogger(__name__)


class IPCNode(node.Node):
    desc = node_types.NodeType()
    desc.name = 'ipc'
    desc.parameter('address', 'string')
    desc.parameter('event_queue_name', 'string')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, address, event_queue_name):
        super().__init__(event_loop)

        self._stream = audio_stream.AudioStreamClient(address)
        self._event_queue_name = event_queue_name

        self._output = ports.AudioOutputPort('out', audio_format.CHANNELS_STEREO)
        self.add_output(self._output)

    async def setup(self):
        await super().setup()
        self._stream.setup()

    async def cleanup(self):
        self._stream.cleanup()
        await super().cleanup()

    def run(self, ctxt):
        request = data.FrameData()
        request.sample_pos = ctxt.sample_pos
        request.duration = ctxt.duration
        request.events = self.pipeline.backend.get_events_for_prefix(
            self._event_queue_name)
        self._stream.send_frame(request)

        response = self._stream.receive_frame()
        assert response.sample_pos == ctxt.sample_pos, (
            response.sample_pos, ctxt.sample_pos)
        assert response.duration == ctxt.duration, (
            response.duration, ctxt.duration)
        ctxt.perf.add_spans(response.perf_data)

        self._output.frame.resize(0)
        self._output.frame.append_samples(
            response.samples, response.num_samples)
        assert len(self._output.frame) <= ctxt.duration
        self._output.frame.resize(ctxt.duration)

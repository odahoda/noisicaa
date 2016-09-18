#!/usr/bin/python3

import asyncio
import logging
import os
import pickle
import random
import threading

from noisicaa.core import ipc
from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from .. import frame
from .. import events
from .. import audio_stream
from .. import data
from .. import audio_format

logger = logging.getLogger(__name__)


class IPCNode(node.Node):
    class_name = 'ipc'

    def __init__(self, event_loop, address, event_queue_name):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out',
                    direction=node_db.PortDirection.Output,
                    channels='stereo'),
            ])

        super().__init__(event_loop, description)

        self._stream = audio_stream.AudioStreamClient(address)
        self._event_queue_name = event_queue_name

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

        output_port = self.outputs['out']
        if response.num_samples:
            output_port.frame.resize(0)
            output_port.frame.append_samples(
                response.samples, response.num_samples)
            assert len(output_port.frame) <= ctxt.duration
            output_port.frame.resize(ctxt.duration)
        else:
            output_port.frame.resize(ctxt.duration)
            output_port.frame.clear()

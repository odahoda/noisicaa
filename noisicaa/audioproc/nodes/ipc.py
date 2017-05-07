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


class IPCNode(node.CustomNode):
    class_name = 'ipc'

    def __init__(self, event_loop, address, event_queue_name):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out_left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out_right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(event_loop, description)

        self.__stream = audio_stream.AudioStreamClient(address)
        self.__event_queue_name = event_queue_name

        self.__out_l = None
        self.__out_r = None

    async def setup(self):
        await super().setup()
        self.__stream.setup()

    async def cleanup(self):
        self.__stream.cleanup()
        await super().cleanup()

    def connect_port(self, port_name, buf, offset):
        if port_name == 'out_left':
            self.__out_l = (buf, offset)
        elif port_name == 'out_right':
            self.__out_r = (buf, offset)
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        request = data.FrameData()
        request.sample_pos = ctxt.sample_pos
        request.duration = ctxt.duration
        request.events = self.pipeline.backend.get_events_for_prefix(
            self.__event_queue_name)
        self.__stream.send_frame(request)
        response = self.__stream.receive_frame()

        assert response.sample_pos == ctxt.sample_pos, (
            response.sample_pos, ctxt.sample_pos)
        assert response.duration == ctxt.duration, (
            response.duration, ctxt.duration)
        ctxt.perf.add_spans(response.perf_data)

        outbuf_l, offset_l = self.__out_l
        outbuf_r, offset_r = self.__out_r

        length = 4 * response.duration
        assert len(response.samples) == 2 * length
        outbuf_l[offset_l:offset_l+length] = response.samples[0:length]
        outbuf_r[offset_r:offset_r+length] = response.samples[length:]

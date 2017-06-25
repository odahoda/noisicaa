#!/usr/bin/python3

import asyncio
import logging
import os
import pickle
import random
import threading

import capnp

from noisicaa.core import ipc
from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. import node
from .. import frame
from .. import events
from .. import audio_stream
from .. import entity_capnp
from .. import frame_data_capnp
from .. import audio_format

logger = logging.getLogger(__name__)


class IPCNode(node.CustomNode):
    class_name = 'ipc'

    def __init__(self, event_loop, address, event_queue_name):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
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

    def connect_port(self, port_name, buf):
        if port_name == 'out:left':
            self.__out_l = buf
        elif port_name == 'out:right':
            self.__out_r = buf
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        request = frame_data_capnp.FrameData.new_message()
        request.samplePos = ctxt.sample_pos
        request.frameSize = ctxt.duration
        # TODO: get (event) buffers for this sheet.
        # request.events = self.pipeline.backend.get_events_for_prefix(
        #     self.__event_queue_name)
        self.__stream.send_frame(request)

        response = self.__stream.receive_frame()
        assert response.samplePos == ctxt.sample_pos, (
            response.samplePos, ctxt.sample_pos)
        assert response.frameSize == ctxt.duration, (
            response.frameSize, ctxt.duration)
        #ctxt.perf.add_spans(response.perf_data)

        for entity in response.entities:
            if entity.id == 'output:left':
                assert entity.size == 4 * response.frameSize
                assert entity.type == entity_capnp.Entity.Type.audio
                self.__out_l[0:entity.size] = entity.data
            elif entity.id == 'output:right':
                assert entity.size == 4 * response.frameSize
                assert entity.type == entity_capnp.Entity.Type.audio
                self.__out_r[0:entity.size] = entity.data

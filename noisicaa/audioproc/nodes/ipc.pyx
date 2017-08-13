#!/usr/bin/python3

from libc cimport string

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
from .. cimport node
from .. import audio_stream
from .. import entity_capnp
from .. import frame_data_capnp
from .. import audio_format

logger = logging.getLogger(__name__)


cdef class IPCNode(node.CustomNode):
    class_name = 'ipc'

    def __init__(self, *, address, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.__stream = audio_stream.AudioStreamClient(address)

        self.__out_l = None
        self.__out_r = None

    def setup(self):
        super().setup()
        self.__stream.setup()

    def cleanup(self):
        self.__stream.cleanup()
        super().cleanup()

    cdef int connect_port(self, port_name, buf) except -1:
        if port_name == 'out:left':
            self.__out_l = buf
        elif port_name == 'out:right':
            self.__out_r = buf
        else:
            raise ValueError(port_name)

        return 0

    cdef int run(self, ctxt) except -1:
        with ctxt.perf.track('ipc'):
            request = frame_data_capnp.FrameData.new_message()
            request.samplePos = ctxt.sample_pos
            request.frameSize = ctxt.duration
            with ctxt.perf.track('ipc.send_frame'):
                self.__stream.send_frame(request)

            with ctxt.perf.track('ipc.receive_frame'):
                response = self.__stream.receive_frame()
            assert response.samplePos == ctxt.sample_pos, (
                response.samplePos, ctxt.sample_pos)
            assert response.frameSize == ctxt.duration, (
                response.frameSize, ctxt.duration)
            ctxt.perf.add_spans(response.perfData)

        for entity in response.entities:
            if entity.id == 'output:left':
                assert entity.type == entity_capnp.Entity.Type.audio
                assert entity.size == 4 * response.frameSize
                string.memmove(self.__out_l.data, <char*>entity.data, entity.size)
            elif entity.id == 'output:right':
                assert entity.type == entity_capnp.Entity.Type.audio
                assert entity.size == 4 * response.frameSize
                string.memmove(self.__out_r.data, <char*>entity.data, entity.size)

        return 0


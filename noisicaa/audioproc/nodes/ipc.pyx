#!/usr/bin/python3

from libc cimport string

import logging
import os
import pickle
import random
import threading

import capnp

import noisicore
from noisicaa.core import ipc
from noisicaa import music
from noisicaa import node_db

from .. import ports
from .. cimport node

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

        self.__stream = noisicore.AudioStream.create_client(address)

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
            request = noisicore.BlockData.new_message()
            request.samplePos = ctxt.sample_pos
            request.blockSize = ctxt.duration
            with ctxt.perf.track('ipc.send_block'):
                self.__stream.send_block(request)

            with ctxt.perf.track('ipc.receive_block'):
                response = self.__stream.receive_block()
            assert response.samplePos == ctxt.sample_pos, (
                response.samplePos, ctxt.sample_pos)
            assert response.blockSize == ctxt.duration, (
                response.blockSize, ctxt.duration)
            ctxt.perf.add_spans(response.perfData)

        for buf in response.buffers:
            if buf.id == 'output:left':
                assert len(buf.data) == 4 * response.blockSize
                string.memmove(self.__out_l.data, <char*>buf.data, len(buf.data))
            elif buf.id == 'output:right':
                assert len(buf.data) == 4 * response.blockSize
                string.memmove(self.__out_r.data, <char*>buf.data, len(buf.data))

        return 0


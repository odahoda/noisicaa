#!/usr/bin/python3

from libc.stdint cimport uint32_t
from libc cimport string

import logging

from noisicaa import node_db

from .. import ports
from .. cimport node
from .. import audio_format

logger = logging.getLogger(__name__)


cdef class PassThru(node.CustomNode):
    class_name = 'passthru'

    def __init__(self, **kwargs):
        description = node_db.SystemNodeDescription(
            ports=[
                node_db.AudioPortDescription(
                    name='in:left',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='in:right',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self.__in_left = None
        self.__in_right = None
        self.__out_left = None
        self.__out_right = None

    cdef int connect_port(self, port_name, buf) except -1:
        if port_name == 'in:left':
            self.__in_left = buf
        elif port_name == 'in:right':
            self.__in_right = buf
        elif port_name == 'out:left':
            self.__out_left = buf
        elif port_name == 'out:right':
            self.__out_right = buf
        else:
            raise ValueError(port_name)

        return 0

    cdef int run(self, ctxt) except -1:
        cdef uint32_t length = 4 * ctxt.duration
        string.memmove(self.__out_left.data, self.__in_left.data, length)
        string.memmove(self.__out_right.data, self.__in_right.data, length)
        return 0


#!/usr/bin/python3

import logging
import struct

import numpy

from noisicaa.bindings import ladspa
from noisicaa import node_db

from .. import ports
from .. cimport node
from .. import audio_format
from ..vm cimport buffers

logger = logging.getLogger(__name__)


cdef class Ladspa(node.CustomNode):
    class_name = 'ladspa'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__library = None
        self.__descriptor = None
        self.__instance = None
        self.__buffers = None

    def setup(self):
        super().setup()

        library_path = self.description.get_parameter('library_path').value
        label = self.description.get_parameter('label').value

        self.__library = ladspa.Library(library_path)
        self.__descriptor = self.__library.get_descriptor(label)
        self.__instance = self.__descriptor.instantiate(44100)
        self.__instance.activate()

        self.__buffers = {}
        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                logger.info("Creating parameter buffer %s...", parameter.name)

                buf = bytearray(4)
                self.__buffers[parameter.name] = buf

                for port in self.__descriptor.ports:
                    if port.name == parameter.name:
                        self.__instance.connect_port(port, <char*>buf)

    def cleanup(self):
        if self.__instance is not None:
            self.__instance.deactivate()
            self.__instance = None

        self.__descriptor = None
        self.__library = None
        self.__buffers = None

        super().cleanup()

    cdef int connect_port(self, port_name, buf) except -1:
        for port in self.__descriptor.ports:
            if port.name == port_name:
                self.__instance.connect_port(port, (<buffers.Buffer>buf).data)
        return 0

    cdef int run(self, ctxt) except -1:
        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                self.__buffers[parameter.name][:] = struct.pack('=f', self.get_param(parameter.name))

        self.__instance.run(ctxt.duration)

        return 0

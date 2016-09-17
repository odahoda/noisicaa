#!/usr/bin/python3

import logging

import numpy

from noisicaa.bindings import ladspa
from noisicaa import node_db

from .. import ports
from .. import node
from .. import audio_format

logger = logging.getLogger(__name__)


class Ladspa(node.Node):
    class_name = 'ladspa'

    def __init__(self, event_loop, description=None, name='ladspa', id=None):
        super().__init__(event_loop, description, name, id)

        self.__library = None
        self.__descriptor = None
        self.__instance = None
        self.__buffers = None

    async def setup(self):
        await super().setup()

        library_path = self._description.get_parameter('library_path').value
        label = self._description.get_parameter('label').value

        self.__library = ladspa.Library(library_path)
        self.__descriptor = self.__library.get_descriptor(label)
        self.__instance = self.__descriptor.instantiate(44100)
        self.__instance.activate()

        self.__buffers = {}
        for port in self.__descriptor.ports:
            initial_length = 1
            if port.type == ladspa.PortType.Audio:
                initial_length = 1024
            buf = numpy.zeros(shape=(initial_length,), dtype=numpy.float32)
            self.__buffers[port.name] = buf
            self.__instance.connect_port(port, buf)

    async def cleanup(self):
        self.__buffers = None

        if self.__instance is not None:
            self.__instance.deactivate()
            self.__instance = None

        self.__descriptor = None
        self.__library = None

        await super().cleanup()

    def run(self, ctxt):
        for port in self.__descriptor.ports:
            buf = self.__buffers[port.name]
            if port.type == ladspa.PortType.Audio:
                required_length = ctxt.duration
            elif port.type == ladspa.PortType.Control:
                required_length = 1
            else:
                raise ValueError

            if len(buf) < required_length:
                buf.resize(required_length)
                self.__instance.connect_port(port, buf)

        for port_name, port in self.inputs.items():
            buf = self.__buffers[port_name]
            if isinstance(port, ports.AudioInputPort):
                numpy.copyto(buf, port.frame.samples[0])
            elif isinstance(port, ports.ControlInputPort):
                buf[0] = port.frame[0]
            else:
                raise ValueError(port)

        for parameter in self._description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                self.__buffers[parameter.name][0] = self.get_param(parameter.name)

        self.__instance.run(ctxt.duration)

        for port_name, port in self.outputs.items():
            buf = self.__buffers[port_name]
            if isinstance(port, ports.AudioOutputPort):
                port.frame.resize(ctxt.duration)
                numpy.copyto(port.frame.samples[0], buf)
            elif isinstance(port, ports.ControlOutputPort):
                port.frame.fill(buf[0])
            else:
                raise ValueError(port)

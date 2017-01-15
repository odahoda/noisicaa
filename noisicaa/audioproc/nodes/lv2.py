#!/usr/bin/python3

import logging
import threading

import lilv
import numpy

from noisicaa import node_db

from .. import ports
from .. import node
from .. import audio_format

logger = logging.getLogger(__name__)


class LV2(node.Node):
    class_name = 'lv2'

    __world = None
    __world_lock = threading.Lock()

    def __init__(self, event_loop, description=None, name='lv2', id=None):
        super().__init__(event_loop, description, name, id)

        self.__plugin = None
        self.__buffers = None

    async def setup(self):
        await super().setup()

        uri = self.description.get_parameter('uri').value
        logger.info("Setting up LV2 plugin %s...", uri)

        with self.__world_lock:
            if self.__world is None:
                logger.info("Creating new LV2 world...")
                self.__world = lilv.World()
                self.__world.load_all()

            logger.info("Loading plugin...")
            plugins = self.__world.get_all_plugins()
            uri_node = self.__world.new_uri(uri)
            self.__plugin = plugins[uri_node]

            logger.info("Creating instance...")
            self.__instance = lilv.Instance(self.__plugin, 44100)
            self.__instance.activate()

        self.__buffers = {}
        for port in self.description.ports:
            initial_length = 1
            if port.port_type == node_db.PortType.Audio:
                initial_length = 10240
            logger.info("Creating port buffer %s (%s floats)...", port.name, initial_length)

            buf = numpy.zeros(shape=(initial_length,), dtype=numpy.float32)
            self.__buffers[port.name] = buf

            lv2_port = self.__plugin.get_port_by_symbol(port.name)
            assert lv2_port is not None, port.name
            self.__instance.connect_port(lv2_port.get_index(), buf)

        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                logger.info("Creating parameter buffer %s...", parameter.name)

                buf = numpy.zeros(shape=(1,), dtype=numpy.float32)
                self.__buffers[parameter.name] = buf

                lv2_port = self.__plugin.get_port_by_symbol(parameter.name)
                assert lv2_port is not None, parameter.name
                self.__instance.connect_port(lv2_port.get_index(), buf)

    async def cleanup(self):
        if self.__instance is not None:
            self.__instance.deactivate()
            self.__instance = None

        self.__plugin = None

        self.__buffers = None

        await super().cleanup()

    def run(self, ctxt):
        for port in self.description.ports:
            buf = self.__buffers[port.name]

            if port.port_type == node_db.PortType.Audio:
                required_length = ctxt.duration
            elif port.type == node_db.PortType.Control:
                required_length = 1
            else:
                raise ValueError

            if len(buf) < required_length:
                buf.resize(required_length, refcheck=False)
                lv2_port = self.__plugin.get_port_by_symbol(port.name)
                assert lv2_port is not None, port.name
                self.__instance.connect_port(lv2_port.get_index(), buf)

        for port_name, port in self.inputs.items():
            buf = self.__buffers[port_name]
            if isinstance(port, ports.AudioInputPort):
                numpy.copyto(buf, port.frame.samples[0])
            elif isinstance(port, ports.ControlInputPort):
                buf[0] = port.frame[0]
            else:
                raise ValueError(port)

        for parameter in self.description.parameters:
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

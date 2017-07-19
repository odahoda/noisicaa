#!/usr/bin/python3

import logging
import threading

import numpy

from noisicaa.bindings import lilv
from noisicaa.bindings import lv2
from noisicaa import node_db

from .. import ports
from .. import node
from .. import audio_format

logger = logging.getLogger(__name__)


class LV2(node.CustomNode):
    class_name = 'lv2'

    __world = None
    __world_lock = threading.Lock()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__plugin = None
        self.__buffers = None

    def setup(self):
        super().setup()

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
            self.__plugin = plugins.get_by_uri(uri_node)
            assert self.__plugin is not None

            logger.info("Creating instance...")
            self.__instance = self.__plugin.instantiate(44100)
            self.__instance.activate()

        self.__buffers = {}
        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                logger.info("Creating parameter buffer %s...", parameter.name)

                buf = numpy.zeros(shape=(1,), dtype=numpy.float32)
                self.__buffers[parameter.name] = buf

                lv2_port = self.__plugin.get_port_by_symbol(self.__world.new_string(parameter.name))
                assert lv2_port is not None, parameter.name
                self.__instance.connect_port(lv2_port.get_index(), buf)

    def cleanup(self):
        if self.__instance is not None:
            self.__instance.deactivate()
            self.__instance = None

        self.__plugin = None

        self.__buffers = None

        super().cleanup()

    def connect_port(self, port_name, buf):
        lv2_port = self.__plugin.get_port_by_symbol(
            self.__world.new_string(port_name))
        assert lv2_port is not None, port_name
        self.__instance.connect_port(lv2_port.get_index(), buf)

    def run(self, ctxt):
        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                self.__buffers[parameter.name][0] = self.get_param(parameter.name)

        self.__instance.run(ctxt.duration)

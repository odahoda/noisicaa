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
            self.__plugin = plugins.get_by_uri(uri_node)
            assert self.__plugin is not None

            logger.info("Creating instance...")
            self.__instance = self.__plugin.instantiate(44100)
            self.__instance.activate()

        self.__buffers = {}
        # for port in self.description.ports:
        #     if port.port_type == node_db.PortType.Audio:
        #         logger.info("Creating audio port buffer %s...", port.name)
        #         buf = numpy.zeros(shape=(10240,), dtype=numpy.float32)
        #         self.__buffers[port.name] = buf

        #     elif port.port_type == node_db.PortType.Control:
        #         logger.info("Creating control port buffer %s...", port.name)
        #         buf = numpy.zeros(shape=(1,), dtype=numpy.float32)
        #         self.__buffers[port.name] = buf

        #     elif port.port_type == node_db.PortType.Events:
        #         logger.info("Creating event port buffer %s...", port.name)
        #         buf = bytearray(4096)
        #         forge = lv2.AtomForge(self.__world.urid_mapper)
        #         self.__buffers[port.name] = (buf, forge)

        #     else:
        #         raise ValueError(port.port_type)

        #     lv2_port = self.__plugin.get_port_by_symbol(self.__world.new_string(port.name))
        #     assert lv2_port is not None, port.name
        #     self.__instance.connect_port(lv2_port.get_index(), buf)

        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                logger.info("Creating parameter buffer %s...", parameter.name)

                buf = numpy.zeros(shape=(1,), dtype=numpy.float32)
                self.__buffers[parameter.name] = buf

                lv2_port = self.__plugin.get_port_by_symbol(self.__world.new_string(parameter.name))
                assert lv2_port is not None, parameter.name
                self.__instance.connect_port(lv2_port.get_index(), buf)

    async def cleanup(self):
        if self.__instance is not None:
            self.__instance.deactivate()
            self.__instance = None

        self.__plugin = None

        self.__buffers = None

        await super().cleanup()

    def connect_port(self, port_name, buf):
        lv2_port = self.__plugin.get_port_by_symbol(
            self.__world.new_string(port_name))
        assert lv2_port is not None, port_name
        self.__instance.connect_port(lv2_port.get_index(), buf)

    def run(self, ctxt):
        # for port_name, port in self.inputs.items():
        #     if isinstance(port, ports.AudioInputPort):
        #         buf = self.__buffers[port_name]
        #         if len(buf) < ctxt.duration:
        #             buf.resize(ctxt.duration, refcheck=False)
        #             lv2_port = self.__plugin.get_port_by_symbol(
        #                 self.__world.new_string(port_name))
        #             assert lv2_port is not None, port_name
        #             self.__instance.connect_port(lv2_port.get_index(), buf)

        #         buf[0:ctxt.duration] = port.frame.samples[0]

        #     elif isinstance(port, ports.ControlInputPort):
        #         buf = self.__buffers[port_name]
        #         buf[0] = port.frame[0]

        #     elif isinstance(port, ports.EventInputPort):
        #         buf, forge = self.__buffers[port_name]
        #         forge.set_buffer(buf, 4096)
        #         with forge.sequence():
        #             for event in port.events:
        #                 sample_pos = event.sample_pos - ctxt.sample_pos
        #                 assert 0 <= sample_pos < ctxt.duration
        #                 if isinstance(event, events.NoteOnEvent):
        #                     forge.write_midi_event(
        #                         sample_pos,
        #                         bytes([0x90, event.note.midi_note, event.volume]), 3)

        #                 elif isinstance(event, events.NoteOffEvent):
        #                     forge.write_midi_event(
        #                         sample_pos,
        #                         bytes([0x80, event.note.midi_note, 0]), 3)
        #                 else:
        #                     raise NotImplementedError(
        #                         "Event class %s not supported" % type(event).__name__)

        #     else:
        #         raise ValueError(port)

        for parameter in self.description.parameters:
            if parameter.param_type == node_db.ParameterType.Float:
                self.__buffers[parameter.name][0] = self.get_param(parameter.name)

        self.__instance.run(ctxt.duration)

        # for port_name, port in self.outputs.items():
        #     buf = self.__buffers[port_name]
        #     if isinstance(port, ports.AudioOutputPort):
        #         port.frame.resize(ctxt.duration)
        #         port.frame.samples[0] = buf[0:ctxt.duration]
        #     elif isinstance(port, ports.ControlOutputPort):
        #         port.frame.fill(buf[0])
        #     else:
        #         raise ValueError(port)

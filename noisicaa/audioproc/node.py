#!/usr/bin/python3

import logging
import uuid

from noisicaa import node_db

from .exceptions import Error
from . import audio_format
from . import ports

logger = logging.getLogger(__name__)


class Node(object):
    class_name = None

    init_ports_from_description = True
    init_parameters_from_description = True

    def __init__(self, event_loop, description, name=None, id=None):
        assert isinstance(description, node_db.NodeDescription)

        self.event_loop = event_loop
        self._description = description
        self._name = name or type(self).__name__
        self.id = id or uuid.uuid4().hex

        self.pipeline = None
        self.inputs = {}
        self.outputs = {}

        self.__parameters = {}

        if self.init_ports_from_description:
            self.init_ports()
        if self.init_parameters_from_description:
            self.init_parameters()

    @property
    def name(self):
        return self._name

    def init_ports(self):
        port_cls_map = {
            (node_db.PortType.Audio,
             node_db.PortDirection.Input): ports.AudioInputPort,
            (node_db.PortType.Audio,
             node_db.PortDirection.Output): ports.AudioOutputPort,
            (node_db.PortType.Control,
             node_db.PortDirection.Input): ports.ControlInputPort,
            (node_db.PortType.Control,
             node_db.PortDirection.Output): ports.ControlOutputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Input): ports.EventInputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Output): ports.EventOutputPort,
        }

        for port_desc in self._description.ports:
            port_cls = port_cls_map[
                (port_desc.port_type, port_desc.direction)]
            kwargs = {}

            if (port_desc.direction == node_db.PortDirection.Output
                    and port_desc.port_type == node_db.PortType.Audio):
                if port_desc.bypass_port is not None:
                    kwargs['bypass_port'] = port_desc.bypass_port
                if port_desc.drywet_port is not None:
                    kwargs['drywet_port'] = port_desc.drywet_port

            if (port_desc.direction == node_db.PortDirection.Input
                    and port_desc.port_type == node_db.PortType.Events):
                kwargs['csound_instr'] = port_desc.csound_instr

            if (port_desc.port_type == node_db.PortType.Audio):
                if len(port_desc.channels) == 1:
                    kwargs['channels'] = audio_format.CHANNELS_MONO
                elif len(port_desc.channels) == 2:
                    kwargs['channels'] = audio_format.CHANNELS_STEREO
                else:
                    raise ValueError(port_desc.channels)

            port = port_cls(port_desc.name, **kwargs)
            if port_desc.direction == node_db.PortDirection.Input:
                self.add_input(port)
            else:
                self.add_output(port)

    def init_parameters(self):
        for parameter in self._description.parameters:
            if parameter.param_type in (
                    node_db.ParameterType.Float,
                    node_db.ParameterType.String,
                    node_db.ParameterType.Text):
                self.__parameters[parameter.name] = {
                    'value': parameter.default,
                    'description': parameter,
                }
            elif parameter.param_type == node_db.ParameterType.Internal:
                pass
            else:
                raise ValueError(parameter)

    def set_param(self, **kwargs):
        for parameter_name, value in kwargs.items():
            assert parameter_name in self.__parameters
            parameter = self.__parameters[parameter_name]['description']
            if parameter.param_type == node_db.ParameterType.Float:
                assert isinstance(value, float), type(value)
                self.__parameters[parameter_name]['value'] = value
            elif parameter.param_type == node_db.ParameterType.Text:
                assert isinstance(value, str), type(value)
                self.__parameters[parameter_name]['value'] = value
            else:
                raise ValueError(parameter)

    def get_param(self, parameter_name):
        return self.__parameters[parameter_name]['value']

    def send_notification(self, notification):
        self.pipeline.add_notification(self.id, notification)

    def add_input(self, port):
        if not isinstance(port, ports.InputPort):
            raise Error("Must be InputPort")
        port.owner = self
        self.inputs[port.name] = port

    def add_output(self, port):
        if not isinstance(port, ports.OutputPort):
            raise Error("Must be OutputPort")
        port.owner = self
        self.outputs[port.name] = port

    @property
    def parent_nodes(self):
        parents = []
        for port in self.inputs.values():
            for upstream_port in port.inputs:
                parents.append(upstream_port.owner)
        return parents

    async def setup(self):
        """Set up the node.

        Any expensive initialization should go here.
        """
        logger.info("%s: setup()", self.name)

    async def cleanup(self):
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def collect_inputs(self, ctxt):
        for port in self.inputs.values():
            port.collect_inputs(ctxt)

    def post_run(self, ctxt):
        for port in self.outputs.values():
            port.post_run(ctxt)

    def run(self, ctxt):
        raise NotImplementedError


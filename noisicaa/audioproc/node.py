#!/usr/bin/python3

import itertools
import logging
import uuid

from noisicaa import node_db

from .exceptions import Error
from . import ports
from .vm import ast
from .vm import buffers

logger = logging.getLogger(__name__)


class Node(object):
    class_name = None

    init_ports_from_description = True
    init_parameters_from_description = True

    def __init__(self, *, description, id, name=None):
        assert isinstance(description, node_db.NodeDescription), description

        self.description = description
        self._name = name or type(self).__name__
        self.id = id

        self.pipeline = None
        self.broken = False
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
            (node_db.PortType.ARateControl,
             node_db.PortDirection.Input): ports.ARateControlInputPort,
            (node_db.PortType.ARateControl,
             node_db.PortDirection.Output): ports.ARateControlOutputPort,
            (node_db.PortType.KRateControl,
             node_db.PortDirection.Input): ports.KRateControlInputPort,
            (node_db.PortType.KRateControl,
             node_db.PortDirection.Output): ports.KRateControlOutputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Input): ports.EventInputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Output): ports.EventOutputPort,
        }

        for port_desc in self.description.ports:
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

            port = port_cls(port_desc.name, **kwargs)
            if port_desc.direction == node_db.PortDirection.Input:
                self.add_input(port)
            else:
                self.add_output(port)

    def init_parameters(self):
        for parameter in self.description.parameters:
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

    def setup(self):
        """Set up the node.

        Any expensive initialization should go here.
        """
        logger.info("%s: setup()", self.name)

    def cleanup(self):
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def get_ast(self, compiler):
        seq = ast.Sequence()

        for parameter_name, parameter_desc in sorted(self.__parameters.items()):
            buf_name = '%s:param:%s' % (self.id, parameter_name)
            seq.add(ast.AllocBuffer(buf_name, buffers.Float()))
            seq.add(ast.FetchParameter(buf_name, buf_name))

        for port in itertools.chain(
                self.inputs.values(), self.outputs.values()):
            seq.add(ast.AllocBuffer(
                port.buf_name, port.get_buf_type(compiler)))

        for port in self.inputs.values():
            seq.add(ast.ClearBuffer(port.buf_name))
            for upstream_port in port.inputs:
                seq.add(ast.MixBuffers(
                    upstream_port.buf_name, port.buf_name))

        return seq


class CustomNode(Node):
    def get_ast(self, compiler):
        seq = super().get_ast(compiler)
        for port in itertools.chain(
                self.inputs.values(), self.outputs.values()):
            seq.add(ast.ConnectPort(self.id, port.name, port.buf_name))

        seq.add(ast.CallNode(self.id))
        return seq

    def connect_port(self, port_name, buf):
        raise NotImplementedError(type(self))

    def run(self, ctxt):
        raise NotImplementedError(type(self))


class BuiltinNode(Node):
    pass

#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging

from noisicaa import node_db

from .exceptions import Error
from . import vm
from . import ports

logger = logging.getLogger(__name__)


class Node(object):
    class_name = None

    init_ports_from_description = True
    init_parameters_from_description = True

    def __init__(self, *, host_data, description, id, name=None, initial_parameters=None):
        assert isinstance(description, node_db.NodeDescription), description

        self._host_data = host_data
        self.description = description
        self.name = name or type(self).__name__
        self.id = id
        self._initial_parameters = initial_parameters

        self.pipeline = None
        self.broken = False
        self.ports = []
        self.inputs = {}
        self.outputs = {}

        self.__control_values = {}
        self.__parameters = {}

        if self.init_ports_from_description:
            self.init_ports()
        if self.init_parameters_from_description:
            self.init_parameters()

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

            port = port_cls(description=port_desc, **kwargs)
            port.owner = self

            self.ports.append(port)
            if port_desc.direction == node_db.PortDirection.Input:
                self.inputs[port.name] = port
            else:
                self.outputs[port.name] = port

    def init_parameters(self):
        for parameter in self.description.parameters:
            self.__parameters[parameter.name] = {
                'value': parameter.default,
                'description': parameter,
            }

        if self._initial_parameters is not None:
            self.set_param(**self._initial_parameters)

    def set_param(self, **kwargs):
        for parameter_name, value in kwargs.items():
            assert parameter_name in self.__parameters, parameter_name
            parameter = self.__parameters[parameter_name]['description']
            if parameter.param_type == node_db.ParameterType.Int:
                assert isinstance(value, int), type(value)
                self.__parameters[parameter_name]['value'] = value
            elif parameter.param_type == node_db.ParameterType.Float:
                assert isinstance(value, float), type(value)
                self.__parameters[parameter_name]['value'] = value
            elif parameter.param_type in (node_db.ParameterType.Text,
                                          node_db.ParameterType.String,
                                          node_db.ParameterType.Path):
                assert isinstance(value, str), type(value)
                self.__parameters[parameter_name]['value'] = value
            else:
                raise ValueError(parameter_name)

    def get_param(self, parameter_name):
        return self.__parameters[parameter_name]['value']

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

        for port in self.ports:
            if isinstance(port, ports.KRateControlInputPort):
                logger.info("Float control value '%s'", port.buf_name)
                self.__control_values[port.buf_name] = vm.FloatControlValue(
                    port.buf_name, port.description.default)

    def cleanup(self):
        """Clean up the node.

        The counterpart of setup().
        """
        logger.info("%s: cleanup()", self.name)

    def get_processor(self):
        return None

    @property
    def control_values(self):
        return [v for _, v in sorted(self.__control_values.items())]

    def add_to_spec(self, spec):
        for cv in self.control_values:
            spec.append_control_value(cv)

        for port in self.ports:
            spec.append_buffer(port.buf_name, port.get_buf_type())

            if port.buf_name in self.__control_values:
                spec.append_opcode(
                    'FETCH_CONTROL_VALUE', self.__control_values[port.buf_name], port.buf_name)
            elif isinstance(port, ports.InputPort):
                spec.append_opcode('CLEAR', port.buf_name)
                for upstream_port in port.inputs:
                    spec.append_opcode('MIX', upstream_port.buf_name, port.buf_name)


class ProcessorNode(Node):
    class_name = 'processor'
    init_parameters_from_description = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        assert isinstance(self.description, node_db.ProcessorDescription)
        self.__processor = None

    def get_processor(self):
        return self.__processor

    def setup(self):
        super().setup()

        spec = vm.ProcessorSpec()
        spec.init(self.description)

        self.__processor = vm.Processor(
            self.id,
            self._host_data,
            self.description.processor_name,
            spec)

        if self._initial_parameters is not None:
            self.set_param(**self._initial_parameters)

        self.__processor.setup()

    def cleanup(self):
        if self.__processor is not None:
            self.__processor.cleanup()
            self.__processor = None

        super().cleanup()

    def set_param(self, **kwargs):
        for parameter_name, value in kwargs.items():
            self.__processor.set_parameter(parameter_name, value)

    def get_param(self, parameter_name):
        return self.__processor.get_string_parameter(parameter_name)

    def add_to_spec(self, spec):
        super().add_to_spec(spec)

        spec.append_processor(self.__processor)

        for port_idx, port in enumerate(self.ports):
            spec.append_opcode('CONNECT_PORT', self.__processor, port_idx, port.buf_name)

        spec.append_opcode('CALL', self.__processor)


class BuiltinNode(Node):
    pass

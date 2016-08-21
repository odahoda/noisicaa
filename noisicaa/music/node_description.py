#!/usr/bin/python3

import enum


class NodeDescription(object):
    def __init__(self, ports=None, parameters=None):
        self.ports = []
        if ports is not None:
            self.ports.extend(ports)
        self.parameters = []
        if parameters is not None:
            self.parameters.extend(parameters)


class SystemNodeDescription(NodeDescription):
    pass


class UserNodeDescription(NodeDescription):
    def __init__(self, display_name, node_cls, **kwargs):
        super().__init__(**kwargs)
        self.display_name = display_name
        self.node_cls = node_cls


class PortType(enum.Enum):
    Audio = 'audio'
    Events = 'events'


class PortDirection(enum.Enum):
    Input = 'input'
    Output = 'output'


class PortDescription(object):
    def __init__(self, name, port_type, direction):
        self.name = name
        self.port_type = port_type
        self.direction = direction


class AudioPortDescription(PortDescription):
    def __init__(self, **kwargs):
        super().__init__(port_type=PortType.Audio, **kwargs)


class EventPortDescription(PortDescription):
    def __init__(self, **kwargs):
        super().__init__(port_type=PortType.Events, **kwargs)


class ParameterType(enum.Enum):
    Internal = 'internal'
    String = 'string'
    Path = 'path'
    Text = 'text'


class ParameterDescription(object):
    def __init__(self, name, param_type):
        self.name = name
        self.param_type = param_type


class InternalParameterDescription(ParameterDescription):
    def __init__(self, value, **kwargs):
        super().__init__(param_type=ParameterType.Internal, **kwargs)
        self.value = value


class StringParameterDescription(ParameterDescription):
    def __init__(self, **kwargs):
        super().__init__(param_type=ParameterType.String, **kwargs)


class PathParameterDescription(ParameterDescription):
    def __init__(self, **kwargs):
        super().__init__(param_type=ParameterType.Path, **kwargs)


class TextParameterDescription(ParameterDescription):
    def __init__(self, content_type='text/plain', **kwargs):
        super().__init__(param_type=ParameterType.Text, **kwargs)

        self.content_type = content_type

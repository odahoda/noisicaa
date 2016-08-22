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

    def get_parameter(self, name):
        for parameter in self.parameters:
            if parameter.name == name:
                return parameter
        raise KeyError("No parameter %r." % name)


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
    Float = 'float'


class ParameterDescription(object):
    def __init__(self, param_type, name, display_name=None):
        self.name = name
        self.display_name = display_name or name
        self.param_type = param_type

    def validate(self, value):
        return value

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

class FloatParameterDescription(ParameterDescription):
    def __init__(self, min=0.0, max=1.0, default=0.0, **kwargs):
        super().__init__(param_type=ParameterType.Float, **kwargs)

        self.min = min
        self.max = max
        self.default = default

    def validate(self, value):
        return min(self.max, max(self.min, value))

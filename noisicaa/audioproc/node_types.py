#!/usr/bin/python3


class NodeType(object):
    def __init__(self):
        self.name = None
        self.is_system = False
        self.ports = []
        self.parameters = []

    def port(self, name, direction, port_type):
        self.ports.append((name, direction, port_type))

    def parameter(self, name, value_type):
        self.parameters.append((name, value_type))

    def __str__(self):
        return '<%s>' % self.name
    __repr__ = __str__

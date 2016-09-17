#!/usr/bin/python3


class Mutation(object):
    pass


class AddNode(Mutation):
    def __init__(self, node):
        self.id = node.id
        self.node_description = node.description

    def __str__(self):
        return '<AddNode id="%s" description="%s">' % (self.id, self.node_description)


class RemoveNode(Mutation):
    def __init__(self, node):
        self.id = node.id

    def __str__(self):
        return '<RemoveNode id="%s">' % self.id


class ConnectPorts(Mutation):
    def __init__(self, port1, port2):
        self.node1 = port1.owner.id
        self.port1 = port1.name
        self.node2 = port2.owner.id
        self.port2 = port2.name

    def __str__(self):
        return '<ConnectPorts port1="%s:%s" port2="%s:%s">' % (
            self.node1, self.port1, self.node2, self.port2)


class DisconnectPorts(Mutation):
    def __init__(self, port1, port2):
        self.node1 = port1.owner.id
        self.port1 = port1.name
        self.node2 = port2.owner.id
        self.port2 = port2.name

    def __str__(self):
        return '<DisonnectPorts port1="%s:%s" port2="%s:%s">' % (
            self.node1, self.port1, self.node2, self.port2)

#!/usr/bin/python3

import enum


class BufferType(enum.Enum):
    FLOATS = 1


class ASTNode(object):
    def __init__(self):
        self.children = []

    def __str__(self):
        return type(self).__name__

    def dump(self, indent=0):
        out = '  ' * indent + str(self) + '\n'
        for child in self.children:
            out += child.dump(indent + 1)
        return out

    def walk(self):
        yield self
        yield from self.children


class Sequence(ASTNode):
    def add(self, node):
        self.children.append(node)


class AllocBuffer(ASTNode):
    def __init__(self, buf_name, buf_type, length):
        super().__init__()

        self.buf_name = buf_name
        self.buf_type = buf_type
        self.length = length

    def __str__(self):
        return '%s(%r, %r, %r)' % (
            super().__str__(),
            self.buf_name, self.buf_type.name, self.length)


class ClearBuffer(ASTNode):
    def __init__(self, buf_name):
        super().__init__()

        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r)' % (
            super().__str__(),
            self.buf_name)


class MixBuffers(ASTNode):
    def __init__(self, src_buf_name, dest_buf_name):
        super().__init__()

        self.src_buf_name = src_buf_name
        self.dest_buf_name = dest_buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.src_buf_name, self.dest_buf_name)


class ConnectPort(ASTNode):
    def __init__(self, node_id, port_name, buf_name):
        super().__init__()

        self.node_id = node_id
        self.port_name = port_name
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r, %r)' % (
            super().__str__(),
            self.node_id, self.port_name, self.buf_name)


class CallNode(ASTNode):
    def __init__(self, node_id):
        super().__init__()

        self.node_id = node_id

    def __str__(self):
        return '%s(%r)' % (super().__str__(), self.node_id)


class OutputStereo(ASTNode):
    pass

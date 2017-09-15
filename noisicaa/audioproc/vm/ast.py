#!/usr/bin/python3


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
        for child in self.children:
            yield from child.walk()

    def get_opcodes(self):
        return []


class Sequence(ASTNode):
    def add(self, node):
        self.children.append(node)


class AllocBuffer(ASTNode):
    def __init__(self, buf_name, buf_type):
        super().__init__()

        self.buf_name = buf_name
        self.buf_type = buf_type

    def __str__(self):
        return '%s(%r, %s)' % (
            super().__str__(),
            self.buf_name, self.buf_type)


class ClearBuffer(ASTNode):
    def __init__(self, buf_name):
        super().__init__()

        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r)' % (
            super().__str__(),
            self.buf_name)

    def get_opcodes(self):
        return [
            ('CLEAR', self.buf_name),
        ]


class MixBuffers(ASTNode):
    def __init__(self, src_buf_name, dest_buf_name):
        super().__init__()

        self.src_buf_name = src_buf_name
        self.dest_buf_name = dest_buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.src_buf_name, self.dest_buf_name)

    def get_opcodes(self):
        return [
            ('MIX', self.src_buf_name, self.dest_buf_name),
        ]


class ConnectPort(ASTNode):
    def __init__(self, processor, port_idx, buf_name):
        super().__init__()

        self.processor = processor
        self.port_idx = port_idx
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r, %r)' % (
            super().__str__(),
            self.processor, self.port_idx, self.buf_name)

    def get_opcodes(self):
        return [
            ('CONNECT_PORT', self.processor, self.port_idx, self.buf_name),
        ]


class CallNode(ASTNode):
    def __init__(self, processor):
        super().__init__()

        self.processor = processor

    def __str__(self):
        return '%s(%r)' % (super().__str__(), self.processor)

    def get_opcodes(self):
        return [
            ('CALL', self.processor),
        ]


class Output(ASTNode):
    def __init__(self, buf_name, channel):
        super().__init__()

        self.buf_name = buf_name
        self.channel = channel

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.buf_name, self.channel)

    def get_opcodes(self):
        return [
            ('OUTPUT', self.buf_name, self.channel),
        ]


class FetchBuffer(ASTNode):
    def __init__(self, buffer_id, buf_name):
        super().__init__()

        self.buffer_id = buffer_id
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.buffer_id, self.buf_name)

    def get_opcodes(self):
        return [
            ('FETCH_BUFFER', self.buffer_id, self.buf_name),
        ]

class FetchParameter(ASTNode):
    def __init__(self, parameter_name, buf_name):
        super().__init__()

        self.parameter_name = parameter_name
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.parameter_name, self.buf_name)

    def get_opcodes(self):
        return [
            ('FETCH_PARAMETER', self.parameter_name, self.buf_name),
        ]

class FetchMessages(ASTNode):
    def __init__(self, labelset, buf_name):
        super().__init__()

        self.labelset = labelset
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.labelset, self.buf_name)

    def get_opcodes(self):
        return [
            ('FETCH_MESSAGES', self.labelset, self.buf_name),
        ]

class LogRMS(ASTNode):
    def __init__(self, buf_name):
        super().__init__()

        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r)' % (
            super().__str__(),
            self.buf_name)

    def get_opcodes(self):
        return [
            ('LOG_RMS', self.buf_name),
        ]

class LogAtom(ASTNode):
    def __init__(self, buf_name):
        super().__init__()

        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r)' % (
            super().__str__(),
            self.buf_name)

    def get_opcodes(self):
        return [
            ('LOG_ATOM', self.buf_name),
        ]

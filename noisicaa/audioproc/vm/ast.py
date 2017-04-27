#!/usr/bin/python3

import enum

from . import spec


class BufferType(enum.Enum):
    FLOATS = 1


class BufferRef(object):
    def __init__(self, name, offset, length, type):
        self.name = name
        self.offset = offset
        self.length = length
        self.type = type

    @property
    def num_samples(self):
        assert self.type == BufferType.FLOATS
        assert self.length % 4 == 0
        return self.length // 4

    def __str__(self):
        return '%s (%s): %d@%d' % (
            self.name, self.type.name, self.length, self.offset)


class FloatBufferRef(BufferRef):
    def __init__(self, id, offset, count):
        super().__init__(id, offset, 4 * count, BufferType.FLOATS)


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

    def get_opcodes(self, symbol_table):
        return []


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

    def get_opcodes(self, symbol_table):
        buf_ref = symbol_table.get_buffer(self.buf_name)
        return [
            spec.OpCode(
                'CLEAR_BUFFER',
                offset=buf_ref.offset,
                length=buf_ref.length)
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

    def get_opcodes(self, symbol_table):
        src_ref = symbol_table.get_buffer(self.src_buf_name)
        dest_ref = symbol_table.get_buffer(self.dest_buf_name)
        assert src_ref.num_samples == dest_ref.num_samples
        return [
            spec.OpCode(
                'MIX',
                src_offset=src_ref.offset,
                dest_offset=dest_ref.offset,
                num_samples=src_ref.num_samples)
        ]


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

    def get_opcodes(self, symbol_table):
        buf_ref = symbol_table.get_buffer(self.buf_name)
        node_idx = symbol_table.get_node(self.node_id)
        return [
            spec.OpCode(
                'CONNECT_PORT',
                node_idx=node_idx,
                port_name=self.port_name,
                offset=buf_ref.offset)
        ]


class CallNode(ASTNode):
    def __init__(self, node_id):
        super().__init__()

        self.node_id = node_id

    def __str__(self):
        return '%s(%r)' % (super().__str__(), self.node_id)

    def get_opcodes(self, symbol_table):
        node_idx = symbol_table.get_node(self.node_id)
        return [
            spec.OpCode(
                'CALL',
                node_idx=node_idx)
        ]


class OutputStereo(ASTNode):
    def __init__(self, buf_name_l, buf_name_r):
        super().__init__()

        self.buf_name_l = buf_name_l
        self.buf_name_r = buf_name_r

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.buf_name_l, self.buf_name_r)

    def get_opcodes(self, symbol_table):
        ref_l = symbol_table.get_buffer(self.buf_name_l)
        ref_r = symbol_table.get_buffer(self.buf_name_r)
        assert ref_l.num_samples == ref_r.num_samples
        return [
            spec.OpCode(
                'OUTPUT_STEREO',
                offset_l=ref_l.offset,
                offset_r=ref_r.offset,
                num_samples=ref_l.num_samples)
        ]


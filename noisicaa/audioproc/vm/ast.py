#!/usr/bin/python3

from . import spec


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

    def get_opcodes(self, symbol_table):  # pylint: disable=unused-argument
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

    def get_opcodes(self, symbol_table):
        buf_idx = symbol_table.get_buffer_idx(self.buf_name)
        return [
            spec.OpCode(
                'CLEAR_BUFFER',
                buf_idx=buf_idx)
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
        src_idx = symbol_table.get_buffer_idx(self.src_buf_name)
        dest_idx = symbol_table.get_buffer_idx(self.dest_buf_name)
        return [
            spec.OpCode(
                'MIX',
                src_idx=src_idx,
                dest_idx=dest_idx)
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
        buf_idx = symbol_table.get_buffer_idx(self.buf_name)
        node_idx = symbol_table.get_node(self.node_id)
        return [
            spec.OpCode(
                'CONNECT_PORT',
                node_idx=node_idx,
                port_name=self.port_name,
                buf_idx=buf_idx)
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
        buf_idx_l = symbol_table.get_buffer_idx(self.buf_name_l)
        buf_idx_r = symbol_table.get_buffer_idx(self.buf_name_r)
        return [
            spec.OpCode(
                'OUTPUT_STEREO',
                buf_idx_l=buf_idx_l,
                buf_idx_r=buf_idx_r)
        ]


class FetchEntity(ASTNode):
    def __init__(self, entity_id, buf_name):
        super().__init__()

        self.entity_id = entity_id
        self.buf_name = buf_name

    def __str__(self):
        return '%s(%r, %r)' % (
            super().__str__(),
            self.entity_id, self.buf_name)

    def get_opcodes(self, symbol_table):
        buf_idx = symbol_table.get_buffer_idx(self.buf_name)
        return [
            spec.OpCode(
                'FETCH_ENTITY',
                entity_id=self.entity_id,
                buf_idx=buf_idx)
        ]

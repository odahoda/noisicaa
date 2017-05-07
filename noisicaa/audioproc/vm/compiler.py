#!/usr/bin/python3

import collections
import enum
import logging
import math
import os
import random
import struct
import sys
import threading
import time

import toposort

from . import ast
from . import spec

logger = logging.getLogger(__name__)


class SymbolTable(object):
    def __init__(self):
        self.__buffers = collections.OrderedDict()
        self.__buffer_size = None
        self.__node_map = {}
        self.__nodes = []

    @property
    def buffer_size(self):
        assert self.__buffer_size is not None
        return self.__buffer_size

    @buffer_size.setter
    def buffer_size(self, value):
        assert self.__buffer_size is None
        self.__buffer_size = value

    def add_buffer(self, ref):
        self.__buffers[ref.name] = ref

    def get_buffer(self, name):
        return self.__buffers[name]

    def add_node(self, node_id):
        node_idx = len(self.__nodes)
        self.__nodes.append(node_id)
        self.__node_map[node_id] = node_idx
        return node_idx

    def get_node(self, node_id):
        return self.__node_map[node_id]

    def nodes(self):
        return self.__nodes[:]

    def dump(self):
        out = ''
        out += 'buffers:\n'
        for buffer_ref in self.__buffers.values():
            out += '  %s\n' % buffer_ref
        out += 'nodes:\n'
        for node_idx, node_id in enumerate(self.__nodes):
            out += '  %s: %s\n' % (node_id, node_idx)
        return out


class Compiler(object):
    def __init__(self, *, graph, frame_size):
        self.__graph = graph
        self.__frame_size = frame_size

    @property
    def frame_size(self):
        return self.__frame_size

    def build_ast(self):
        root = ast.Sequence()

        sorted_nodes = toposort.toposort_flatten(
            {n: set(n.parent_nodes) for n in self.__graph.nodes},
            sort=False)

        for n in sorted_nodes:
            root.add(n.get_ast(self))

        return root

    def build_symbol_table(self, root):
        symbol_table = SymbolTable()

        offset = 0
        for node in root.walk():
            if isinstance(node, ast.AllocBuffer):
                if node.buf_type == ast.BufferType.FLOATS:
                    length = 4 * node.length
                else:
                    raise ValueError(node.buf_type)

                buffer_ref = ast.BufferRef(
                    node.buf_name, offset, length, node.buf_type)
                symbol_table.add_buffer(buffer_ref)

                offset += length

            elif isinstance(node, ast.CallNode):
                symbol_table.add_node(node.node_id)

        symbol_table.buffer_size = offset
        return symbol_table

    def build_spec(self, root, symbol_table):
        s = spec.PipelineVMSpec()
        s.nodes = symbol_table.nodes()
        s.buffer_size = symbol_table.buffer_size

        for node in root.walk():
            s.opcodes.extend(node.get_opcodes(symbol_table))

        return s


def compile_graph(*, graph, frame_size):
    compiler = Compiler(graph=graph, frame_size=frame_size)
    ast = compiler.build_ast()
    symbol_table = compiler.build_symbol_table(ast)
    spec = compiler.build_spec(ast, symbol_table)
    return spec

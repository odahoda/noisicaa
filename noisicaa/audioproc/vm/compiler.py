#!/usr/bin/python3

import logging

import toposort

from . import ast
from . import spec

logger = logging.getLogger(__name__)


class SymbolTable(object):
    def __init__(self):
        self.__buffer_map = {}
        self.__buffers = []
        self.__node_map = {}
        self.__nodes = []
        self.__parameter_map = {}
        self.__parameters = []

    def add_buffer(self, name, buf_type):
        buf_idx = len(self.__buffers)
        self.__buffers.append(buf_type)
        self.__buffer_map[name] = buf_idx
        return buf_idx

    def get_buffer_idx(self, name):
        return self.__buffer_map[name]

    def buffers(self):
        return self.__buffers[:]

    def add_node(self, node_id):
        node_idx = len(self.__nodes)
        self.__nodes.append(node_id)
        self.__node_map[node_id] = node_idx
        return node_idx

    def get_node(self, node_id):
        return self.__node_map[node_id]

    def nodes(self):
        return self.__nodes[:]

    def add_parameter(self, name, buf_type):
        assert name not in self.__parameter_map
        idx = len(self.__parameters)
        self.__parameters.append(buf_type)
        self.__parameter_map[name] = idx
        return idx

    def get_parameter_idx(self, name):
        return self.__parameter_map[name]

    def parameters(self):
        return self.__parameters[:]

    def dump(self):
        out = ''
        out += 'buffers:\n'
        for idx, buffer_ref in enumerate(self.__buffers):
            out += '  %s: %s\n' % (idx, buffer_ref)
        out += 'parameters:\n'
        for idx, buf_type in enumerate(self.__parameters):
            out += '  %s: %s\n' % (idx, buf_type)
        out += 'nodes:\n'
        for idx, node_id in enumerate(self.__nodes):
            out += '  %s: %s\n' % (node_id, idx)
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

        for node in root.walk():
            if isinstance(node, ast.AllocBuffer):
                idx = symbol_table.add_buffer(node.buf_name, node.buf_type)
                logger.info("Added buffer #%d: %s (%s)", idx, node.buf_name, node.buf_type)

            elif isinstance(node, ast.CallNode):
                symbol_table.add_node(node.node_id)

            elif isinstance(node, ast.FetchParameter):
                buf_idx = symbol_table.get_buffer_idx(node.buf_name)
                logger.info(str((node.buf_name, buf_idx, symbol_table.buffers())))
                buf_type = symbol_table.buffers()[buf_idx]
                symbol_table.add_parameter(node.parameter_name, buf_type)

        return symbol_table

    def build_spec(self, root, symbol_table):
        s = spec.PipelineVMSpec()
        s.buffers = symbol_table.buffers()
        s.nodes = symbol_table.nodes()

        for node in root.walk():
            s.opcodes.extend(node.get_opcodes(symbol_table))

        return s


def compile_graph(*, graph, frame_size):
    compiler = Compiler(graph=graph, frame_size=frame_size)
    ast = compiler.build_ast()
    logger.info(ast.dump())
    symbol_table = compiler.build_symbol_table(ast)
    spec = compiler.build_spec(ast, symbol_table)
    return spec

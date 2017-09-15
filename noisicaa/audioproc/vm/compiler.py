#!/usr/bin/python3

import logging

import toposort

import noisicore
from . import ast

logger = logging.getLogger(__name__)


class Compiler(object):
    def __init__(self, *, graph):
        self.__graph = graph

    def build_ast(self):
        root = ast.Sequence()

        sorted_nodes = toposort.toposort_flatten(
            {n: set(n.parent_nodes) for n in self.__graph.nodes},
            sort=False)

        for n in sorted_nodes:
            root.add(n.get_ast())

        return root

    def build_spec(self, root):
        spec = noisicore.Spec()

        for node in root.walk():
            if isinstance(node, ast.AllocBuffer):
                logger.info("Add buffer: %s (%s)", node.buf_name, node.buf_type)
                spec.append_buffer(node.buf_name, node.buf_type)

            elif isinstance(node, ast.CallNode):
                logger.info("Add processor: %s", node.processor.id)
                spec.append_processor(node.processor)

            # elif isinstance(node, ast.FetchParameter):
            #     buf_idx = symbol_table.get_buffer_idx(node.buf_name)
            #     logger.info(str((node.buf_name, buf_idx, symbol_table.buffers())))
            #     buf_type = symbol_table.buffers()[buf_idx]
            #     symbol_table.add_parameter(node.parameter_name, buf_type)

        for node in root.walk():
            for opcode, *opargs in node.get_opcodes():
                logger.info("Add opcode: %s(%s)", opcode, ', '.join(str(a) for a in opargs))
                spec.append_opcode(opcode, *opargs)

        return spec


def compile_graph(*, graph):
    compiler = Compiler(graph=graph)
    ast = compiler.build_ast()
    logger.info(ast.dump())
    spec = compiler.build_spec(ast)
    return spec

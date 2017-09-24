#!/usr/bin/python3

import logging

import toposort

import noisicore

logger = logging.getLogger(__name__)


class Compiler(object):
    def __init__(self, *, graph):
        self.__graph = graph

    def build_spec(self):
        spec = noisicore.Spec()

        sorted_nodes = toposort.toposort_flatten(
            {node: set(node.parent_nodes) for node in self.__graph.nodes},
            sort=False)

        for node in sorted_nodes:
            node.add_to_spec(spec)

        return spec


def compile_graph(*, graph):
    compiler = Compiler(graph=graph)
    spec = compiler.build_spec()
    return spec

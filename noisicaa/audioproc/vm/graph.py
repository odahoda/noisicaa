#!/usr/bin/python3

import logging

logger = logging.getLogger(__name__)


class PipelineGraph(object):
    def __init__(self):
        self.__nodes = {}

    @property
    def nodes(self):
        return set(self.__nodes.values())

    def find_node(self, node_id):
        return self.__nodes[node_id]

    def add_node(self, node):
        self.__nodes[node.id] = node

    def remove_node(self, node):
        del self.__nodes[node.id]

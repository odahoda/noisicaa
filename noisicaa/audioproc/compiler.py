#!/usr/bin/python3

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

logger = logging.getLogger(__name__)


class Compiler(object):
    def __init__(self, graph):
        self.__graph = graph

    def build_ast(self):
        root = ast.Sequence()

        sorted_nodes = toposort.toposort_flatten(
            {n: set(n.parent_nodes) for n in self.__graph.nodes},
            sort=False)

        for n in sorted_nodes:
            root.children.append(n.get_ast())

        return root

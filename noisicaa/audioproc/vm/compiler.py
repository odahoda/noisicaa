#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging

import toposort

from noisicaa.audioproc import vm

logger = logging.getLogger(__name__)


class Compiler(object):
    def __init__(self, *, graph):
        self.__graph = graph

    def build_spec(self):
        spec = vm.Spec()

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

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

from typing import List

from noisicaa import node_db
from noisicaa import host_system as host_system_lib
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine import buffer_arena
from noisicaa.audioproc.engine import block_context
from noisicaa.audioproc.engine import processor


# We actually use memoryviews, but mypy doesn't know that a memoryview can also behave like an
# array of floats.
BufferView = List


class BufferManager(object):
    def __init__(
            self,
            host_system: host_system_lib.HostSystem ,
            arena: buffer_arena.PyBufferArena = None,
            size: int = 2**20) -> None:
        ...
    def allocate_from_node_description(
            self, node_description: node_db.NodeDescription, prefix: str = '') -> None: ...
    def connect_ports(
            self,
            proc: processor.PyProcessor,
            ctxt: block_context.PyBlockContext,
            node_description: node_db.NodeDescription,
           prefix: str = '') -> None: ...
    def allocate(self, name: str, type: buffers.PyBufferType) -> BufferView: ...
    def __getitem__(self, name: str) -> BufferView: ...
    def type(self, name: str) -> buffers.PyBufferType: ...
    def data(self, name: str) -> memoryview: ...

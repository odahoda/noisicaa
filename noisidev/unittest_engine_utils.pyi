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

from noisicaa import node_db
from noisicaa.host_system.host_system import PyHostSystem
from noisicaa.audioproc.engine import buffers
from noisicaa.audioproc.engine.buffer_arena import PyBufferArena
from noisicaa.audioproc.engine.block_context import PyBlockContext
from noisicaa.audioproc.engine.processor import PyProcessor


class BufferManager(object):
    def __init__(
            self,
            host_system: PyHostSystem ,
            arena: PyBufferArena = None,
            size: int = 2**20) -> None:
        ...
    def allocate_from_node_description(
            self, node_description: node_db.NodeDescription, prefix: str = '') -> None: ...
    def connect_ports(
            self,
            proc: PyProcessor,
            ctxt: PyBlockContext,
            node_description: node_db.NodeDescription,
           prefix: str = '') -> None: ...
    def allocate(self, name: str, type: buffers.PyBufferType) -> memoryview: ...
    def __getitem__(self, name: str) -> memoryview: ...
    def type(self, name: str) -> buffers.PyBufferType: ...
    def data(self, name: str) -> memoryview: ...

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import enum

from noisicaa import node_db
from noisicaa import audioproc
from noisicaa import host_system as host_system_lib
from noisicaa.audioproc.public import node_parameters_pb2
from . import block_context
from . import buffers


class State(enum.Enum):
    INACTIVE = ...  # type: State
    SETUP = ...  # type: State
    RUNNING = ...  # type: State
    BROKEN = ...  # type: State
    CLEANUP = ...  # type: State


class PyProcessor(object):
    def __init__(
            self, realm_name: str, node_id: str, host_system: host_system_lib.HostSystem,
            node_description: node_db.NodeDescription) -> None: ...
    @property
    def id(self) -> int: ...
    @property
    def state(self) -> State: ...
    def setup(self) -> None: ...
    def cleanup(self) -> None: ...
    def connect_port(
            self, ctxt: block_context.PyBlockContext, port_index: int, buffer: buffers.PyBuffer) -> None: ...
    def process_block(
            self, ctxt: block_context.PyBlockContext, time_mapper: audioproc.TimeMapper) -> None: ...
    def handle_message(self, msg: audioproc.ProcessorMessage) -> None: ...
    def set_parameters(self, parameters: node_parameters_pb2.NodeParameters) -> None: ...
    def set_description(self, desc: node_db.NodeDescription) -> None: ...

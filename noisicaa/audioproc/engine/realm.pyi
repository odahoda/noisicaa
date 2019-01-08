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

from typing import Dict, List, Optional

from noisicaa import core
from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import node_db
from noisicaa import host_system as host_system_lib
from noisicaa.audioproc.public import engine_notification_pb2
from . import player as player_lib
from . import spec as spec_lib
from . import processor
from . import control_value as control_value_lib
from . import block_context as block_context_lib
from . import buffers
from . import processor
from . import graph as graph_lib
from . import engine as engine_lib

# We actually use memoryviews, but mypy doesn't know that a memoryview can also behave like an
# array of floats.
BufferView = List


class PyProgram(object):
    pass


class PyRealm(object):
    notifications = ...  # type: core.Callback[engine_notification_pb2.EngineNotification]
    child_realms = ...  # type: Dict[str, PyRealm]

    def __init__(
            self, *, engine: engine_lib.Engine, name: str, parent: PyRealm,
            host_system: host_system_lib.HostSystem, player: player_lib.PyPlayer,
            callback_address: str) -> None: ...
    @property
    def name(self) -> str: ...
    @property
    def parent(self) -> PyRealm: ...
    @property
    def graph(self) -> graph_lib.Graph: ...
    @property
    def player(self) -> player_lib.PyPlayer: ...
    @property
    def callback_address(self) -> str: ...
    @property
    def block_context(self) -> block_context_lib.PyBlockContext: ...
    async def setup(self) -> None: ...
    async def cleanup(self) -> None: ...
    def clear_programs(self) -> None: ...
    def get_buffer(self, name: str, type: buffers.PyBufferType) -> BufferView: ...
    async def get_plugin_host(self) -> ipc.Stub: ...
    def update_spec(self) -> None: ...
    def set_spec(self, spec: spec_lib.PySpec) -> None: ...
    async def setup_node(self, node: graph_lib.Node) -> None: ...
    def add_active_processor(self, proc: processor.PyProcessor) -> None: ...
    def add_active_control_value(self, control_value: control_value_lib.PyControlValue) -> None: ...
    def add_active_child_realm(self, child: PyRealm) -> None: ...
    def set_control_value(self, name: str, value: float, generation: int) -> None: ...
    async def set_plugin_state(self, node: str, state: audioproc.PluginState) -> None: ...
    def send_node_message(self, msg: audioproc.ProcessorMessage) -> None: ...
    def update_project_properties(
            self, *, bpm: Optional[int] = None,
            duration: Optional[audioproc.MusicalDuration] = None) -> None: ...
    def get_active_program(self) -> Optional[PyProgram]: ...
    def process_block(self, program: PyProgram) -> None: ...
    def run_maintenance(self) -> None: ...

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

from typing import Callable, List, Tuple

from noisicaa import host_system as host_system_lib
from noisicaa import audioproc
from . import plugin_ui_host
from . import plugin_host_pb2


def build_memory_mapping(
        shmem_path: str, cond_offset: int, block_size: int, buffers: List[Tuple[int, int]]
) -> bytearray: ...
def init_cond(buf: memoryview, offset: int) -> int: ...
def cond_wait(buf: memoryview, offset: int) -> None: ...
def cond_clear(buf: memoryview, offset: int) -> None: ...


class PyPluginHost(object):
    def __init__(
            self, spec: plugin_host_pb2.PluginInstanceSpec, host_system: host_system_lib.HostSystem
    ) -> None: ...
    def setup(self) -> None: ...
    def cleanup(self) -> None: ...
    def create_ui(
            self, control_value_change_cb: Callable[[int, float, int], None]
    ) -> plugin_ui_host.PyPluginUIHost: ...
    def main_loop(self, pipe_fd: int) -> None: ...
    def exit_loop(self) -> None: ...
    def connect_port(self, port: int, data: bytearray) -> None: ...
    def process_block(self, block_size: int) -> None: ...
    def has_state(self) -> bool: ...
    def get_state(self) -> audioproc.PluginState: ...
    def set_state(self, state: audioproc.PluginState) -> None: ...

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

from typing import List, Optional, Union

from noisicaa import host_system as host_system_lib
from . import block_context
from . import buffers
from . import realm as realm_lib


class PyBackendSettings(object):
    datastream_address = ...  # type: str
    time_scale = ...  # type: float

    def __init__(
            self, *, datastream_address: Optional[float] = None, time_scale: Optional[float] = None
    ) -> None: ...


class PyBackend(object):
    def __init__(
            self, host_system: host_system_lib.HostSystem, name: Union[str, bytes],
            settings: PyBackendSettings) -> None: ...
    def setup(self, realm: realm_lib.PyRealm) -> None: ...
    def cleanup(self) -> None: ...
    def stop(self) -> None: ...
    def stopped(self) -> bool: ...
    def release(self) -> None: ...
    def released(self) -> bool: ...
    def begin_block(self, ctxt: block_context.PyBlockContext) -> None: ...
    def end_block(self, ctxt: block_context.PyBlockContext) -> None: ...
    def output(
            self, ctxt: block_context.PyBlockContext, channel: str, samples: List) -> None: ...

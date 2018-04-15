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

from typing import Any, Optional, Iterator, List, Set

from . import midi_events


class Error(Exception):
    pass

class APIError(Error):
    def __init__(self, errno: int) -> None: ...


class ClientInfo(object):
    client_id = ...  # type: int
    name = ...  # type: str

    def __init__(self, client_id: int, name: str) -> None: ...


class PortInfo(object):
    client_info = ...  # type: ClientInfo
    port_id = ...  # type: int
    device_id = ...  # type: str
    name = ...  # type: str
    capabilities = ...  # type: Set[str]
    types = ...  # type: Set[str]

    def __init__(
            self, client_info: ClientInfo, port_id: int, name: str, capabilities: Set[str],
            types: Set[str]) -> None: ...


class AlsaSequencer(object):
    def __init__(self, name: str = ...) -> None: ...
    def __enter__(self) -> 'AlsaSequencer': ...
    def __exit__(self, *args: Any) -> bool: ...
    def close(self) -> None: ...
    def list_clients(self) -> Iterator[ClientInfo]: ...
    def list_client_ports(self, client_info: ClientInfo) -> Iterator[PortInfo]: ...
    def list_all_ports(self) -> Iterator[PortInfo]: ...
    def connect(self, port_info: PortInfo) -> None: ...
    def disconnect(self, port_info: PortInfo) -> None: ...
    def get_pollin_fds(self) -> List[int]: ...
    def get_event(self) -> Optional[midi_events.MidiEvent]: ...

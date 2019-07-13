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

from typing import List

from noisicaa import node_db
from noisicaa import host_system

class PyBufferType(object):
    @property
    def view_type(self) -> str: ...


class PyFloatControlValueBuffer(PyBufferType):
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
    @property
    def view_type(self) -> str: ...


class PyFloatAudioBlockBuffer(PyBufferType):
    def __init__(self, type: node_db.PortDescription.Type) -> None: ...
    def __str__(self) -> str: ...
    @property
    def view_type(self) -> str: ...


class PyAtomDataBuffer(PyBufferType):
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
    @property
    def view_type(self) -> str: ...


class PyPluginCondBuffer(PyBufferType):
    def __init__(self) -> None: ...
    def __str__(self) -> str: ...
    @property
    def view_type(self) -> str: ...
    def set_cond(self, buf: List) -> None: ...
    def clear_cond(self, buf: List) -> None: ...
    def wait_cond(self, buf: List) -> None: ...


class PyBuffer(object):
    def __init__(self, host_system: host_system.HostSystem, buf_type: PyBufferType, buf: bytes) -> None: ...

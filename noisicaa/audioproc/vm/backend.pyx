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

_UNSET = object()

cdef class PyBackendSettings(object):
    def __init__(self, *, ipc_address=_UNSET, block_size=2048, time_scale=1.0):
        if ipc_address is not _UNSET:
            self.ipc_address = ipc_address
        if block_size is not _UNSET:
            self.block_size = block_size
        if time_scale is not _UNSET:
            self.time_scale = time_scale

    cdef BackendSettings get(self):
        return self.__settings

    @property
    def ipc_address(self):
        return bytes(self.__settings.ipc_address).decode('utf-8')

    @ipc_address.setter
    def ipc_address(self, value):
        self.__settings.ipc_address = value.encode('utf-8')

    @property
    def block_size(self):
        return int(self.__settings.block_size)

    @block_size.setter
    def block_size(self, value):
        self.__settings.block_size = <uint32_t>value

    @property
    def time_scale(self):
        return float(self.__settings.time_scale)

    @time_scale.setter
    def time_scale(self, value):
        self.__settings.time_scale = <float>value

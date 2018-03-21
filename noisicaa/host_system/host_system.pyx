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

from noisicaa.core.status cimport check


cdef class PyHostSystem(object):
    def __init__(self, mapper):
        self.__urid_mapper = mapper
        self.__host_system_ptr.reset(new HostSystem(self.__urid_mapper.get()))
        self.__host_system = self.__host_system_ptr.get()

    def setup(self):
        check(self.__host_system.setup())

    def cleanup(self):
        self.__host_system.cleanup()

    cdef HostSystem* get(self):
        return self.__host_system

    @property
    def block_size(self):
        return self.__host_system.block_size()

    def set_block_size(self, block_size):
        self.__host_system.set_block_size(block_size)

    @property
    def sample_rate(self):
        return self.__host_system.sample_rate()

    def set_sample_rate(self, sample_rate):
        self.__host_system.set_sample_rate(sample_rate)

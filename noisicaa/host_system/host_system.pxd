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

from libc.stdint cimport uint32_t
from libcpp.memory cimport unique_ptr
from noisicaa.core.status cimport Status
from noisicaa.lv2 cimport urid_mapper


cdef extern from "noisicaa/host_system/host_system.h" namespace "noisicaa" nogil:
    cppclass LV2SubSystem:
        Status setup()
        void cleanup()

    cppclass HostSystem:
        HostSystem(urid_mapper.URIDMapper* mapper)
        Status setup()
        void cleanup()

        uint32_t block_size() const
        uint32_t sample_rate() const
        void set_block_size(uint32_t block_size)
        void set_sample_rate(uint32_t sample_rate)

        unique_ptr[LV2SubSystem] lv2


cdef class PyHostSystem(object):
    cdef urid_mapper.PyURIDMapper __urid_mapper
    cdef unique_ptr[HostSystem] __host_system_ptr
    cdef HostSystem* __host_system

    cdef HostSystem* get(self)

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

from libcpp.memory cimport unique_ptr
from noisicaa.core.status cimport *


cdef extern from "noisicaa/audioproc/vm/host_data.h" namespace "noisicaa" nogil:
    cppclass LV2SubSystem:
        Status setup()
        void cleanup()

    cppclass HostData:
        Status setup()
        void cleanup()

        unique_ptr[LV2SubSystem] lv2;


cdef class PyHostData(object):
    cdef unique_ptr[HostData] __host_data_ptr
    cdef HostData* __host_data

    cdef HostData* ptr(self)

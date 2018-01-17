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

cdef extern from "lv2/lv2plug.in/ns/ext/urid/urid.h" nogil:
    ctypedef uint32_t LV2_URID

cdef extern from "noisicaa/lv2/urid_mapper.h" namespace "noisicaa" nogil:
    cppclass URIDMapper:
        LV2_URID map(const char* uri)
        const char* unmap(LV2_URID urid) const

    cppclass StaticURIDMapper(URIDMapper):
        pass

    cppclass DynamicURIDMapper(URIDMapper):
        pass

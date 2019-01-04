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

from libc.stdint cimport uint8_t
from libc cimport stdlib

from noisicaa.lv2.urid cimport URID_Map_Feature, URID_Unmap_Feature
from noisicaa.lv2.urid_mapper cimport PyURIDMapper
from noisicaa.lv2.atom cimport LV2_Atom


def atom_to_turtle(PyURIDMapper mapper, const uint8_t* atom):
    cdef URID_Map_Feature map = URID_Map_Feature(mapper)
    cdef URID_Unmap_Feature unmap = URID_Unmap_Feature(mapper)

    cdef LV2_Atom* obj = <LV2_Atom*>atom

    cdef Sratom* sratom
    cdef char* turtle
    sratom = sratom_new(&map.data)
    assert sratom != NULL
    try:
        sratom_set_pretty_numbers(sratom, True)

        turtle = sratom_to_turtle(
            sratom, &unmap.data,
            b'http://example.org', NULL, NULL,
            obj.type, obj.size, <void*>(<uint8_t*>(obj) + sizeof(LV2_Atom)))
        try:
            return turtle.decode('utf-8')
        finally:
            stdlib.free(turtle)
    finally:
        sratom_free(sratom)

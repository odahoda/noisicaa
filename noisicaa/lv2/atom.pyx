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

import contextlib
import logging

logger = logging.getLogger(__name__)


cdef class Atom(object):
    def __cinit__(self, PyURIDMapper mapper):
        self.mapper = mapper
        self.atom = NULL

    cdef init(self, LV2_Atom* atom):
        self.atom = atom
        return self

    @staticmethod
    cdef Atom wrap(PyURIDMapper mapper, uint8_t* buf):
        cdef LV2_Atom* atom = <LV2_Atom*>buf
        return Atom(mapper).init(atom)

    def __str__(self):
        return '<Atom type="%s" size=%d>' % (self.type_uri, self.size)
    __repr__ = __str__

    @property
    def type_urid(self):
        return self.atom.type

    @property
    def type_uri(self):
        return self.mapper.unmap(self.type_urid)

    @property
    def size(self):
        return self.atom.size

    @property
    def data(self):
        cdef uint8_t* d = <uint8_t*>self.atom + sizeof(LV2_Atom)
        return bytes(d[:self.size])

    @property
    def as_bytes(self):
        cdef uint8_t* d = <uint8_t*>self.atom
        return bytes(d[:sizeof(LV2_Atom) + self.size])


def wrap_atom(mapper, buf):
    cdef uint8_t* ptr
    cdef char[:] view
    if isinstance(buf, memoryview):
        view = buf
        ptr = <uint8_t*>(&view[0])
    elif isinstance(buf, (bytes, bytearray)):
        ptr = <uint8_t*>buf
    else:
        raise TypeError(type(buf))

    return Atom.wrap(mapper, ptr)

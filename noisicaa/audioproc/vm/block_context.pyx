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

from . cimport musical_time


cdef class PyBlockContext(object):
    def __init__(self):
        self.__perf = PyPerfStats()
        self.__ctxt.perf.reset(self.__perf.release())
        self.__ctxt.out_messages.reset(new MessageQueue())

    cdef BlockContext* get(self) nogil:
        return &self.__ctxt

    @property
    def block_size(self):
        return int(self.__ctxt.block_size)

    @block_size.setter
    def block_size(self, value):
        self.__ctxt.block_size = <uint32_t>value

    @property
    def sample_pos(self):
        return int(self.__ctxt.sample_pos)

    @sample_pos.setter
    def sample_pos(self, value):
        self.__ctxt.sample_pos = <uint32_t>value

    def clear_time_map(self):
        self.__ctxt.time_map.clear()

    def append_sample_time(self, PyMusicalTime start_time, PyMusicalTime end_time):
        cdef SampleTime stime
        stime.start_time = start_time.get()
        stime.end_time = end_time.get()
        self.__ctxt.time_map.push_back(stime)

    @property
    def perf(self):
        return self.__perf

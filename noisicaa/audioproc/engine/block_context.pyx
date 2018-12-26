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

from noisicaa.audioproc.public.musical_time cimport PyMusicalTime
from .buffer_arena cimport PyBufferArena
from . cimport message_queue


cdef class PyBlockContext(object):
    def __init__(self, PyBufferArena buffer_arena=None):
        self.__ptr.reset(new BlockContext())
        self.__ctxt = self.__ptr.get()

        self.__out_messages.reset(new MessageQueue())

        self.__perf = PyPerfStats()
        self.__ctxt.perf.reset(self.__perf.release())
        self.__ctxt.out_messages = self.__out_messages.get()

        if buffer_arena is not None:
            self.__ctxt.buffer_arena = buffer_arena.get()

    @staticmethod
    cdef PyBlockContext create(BlockContext* c_ctxt):
        if c_ctxt == NULL:
            return None

        cdef PyBlockContext ctxt = PyBlockContext.__new__(PyBlockContext)
        ctxt.__ctxt = c_ctxt
        ctxt.__perf = PyPerfStats.create(c_ctxt.perf.get())
        return ctxt

    cdef BlockContext* get(self) nogil:
        return self.__ctxt

    @property
    def sample_pos(self):
        return int(self.__ctxt.sample_pos)

    @sample_pos.setter
    def sample_pos(self, value):
        self.__ctxt.sample_pos = <uint32_t>value

    def create_out_messages(self):
        # TODO: This leaks the MessageQueue instance (but only in unittests)...
        self.__ctxt.out_messages = new MessageQueue()

    def clear_time_map(self, int block_size):
        self.__ctxt.alloc_time_map(block_size)

    def set_sample_time(self, int idx, PyMusicalTime start_time, PyMusicalTime end_time):
        cdef SampleTime* stime = self.__ctxt.time_map.get() + idx
        stime.start_time = start_time.get()
        stime.end_time = end_time.get()

    @property
    def perf(self):
        return self.__perf

    @property
    def out_messages(self):
        cdef message_queue.MessageQueue* queue = self.__ctxt.out_messages
        cdef message_queue.Message* msg = queue.first()
        while not queue.is_end(msg):
            yield message_queue.PyMessage.create(msg)
            msg = queue.next(msg)

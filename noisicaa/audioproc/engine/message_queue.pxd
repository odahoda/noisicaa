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

from libcpp cimport bool

from noisicaa.audioproc.public.musical_time cimport MusicalTime

cdef extern from "noisicaa/audioproc/engine/message_queue.h" namespace "noisicaa" nogil:
    enum MessageType:
        ENGINE_LOAD
        PERF_STATS
        PLAYER_STATE
        NODE_MESSAGE

    cppclass Message:
        MessageType type
        size_t size

    cppclass EngineLoadMessage(Message):
        double load

    cppclass PerfStatsMessage(Message):
        size_t length
        char perf_stats[]

    cppclass PlayerStateMessage(Message):
        char realm[256]
        bool playing
        MusicalTime current_time
        bool loop_enabled
        MusicalTime loop_start_time
        MusicalTime loop_end_time

    cppclass NodeMessage(Message):
        char node_id[256]
        void* atom()

    cppclass MessageQueue:
        void clear()
        Message* first() const
        Message* next(Message* it) const
        int is_end(Message* it) const


cdef class PyMessage(object):
    cdef const Message* __msg

    @staticmethod
    cdef PyMessage create(const Message* msg)

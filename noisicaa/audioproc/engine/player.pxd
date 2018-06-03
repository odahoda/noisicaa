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
from libcpp.memory cimport unique_ptr
from libcpp.string cimport string

from noisicaa.core.status cimport Status
from noisicaa.host_system.host_system cimport HostSystem
from noisicaa.audioproc.public.musical_time cimport MusicalTime

cdef extern from "noisicaa/audioproc/engine/player.h" namespace "noisicaa" nogil:
    cppclass PlayerStateMutation:
        bool set_playing
        bool playing
        bool set_current_time
        MusicalTime current_time
        bool set_loop_enabled
        bool loop_enabled
        bool set_loop_start_time
        MusicalTime loop_start_time
        bool set_loop_end_time
        MusicalTime loop_end_time

    cppclass PlayerState:
        bool playing
        MusicalTime current_time
        bool loop_enabled
        MusicalTime loop_start_time
        MusicalTime loop_end_time

    cppclass Player:
        Player(
            HostSystem* host_system,
            void (*state_callback)(void*, const string&),
            void* userdata)

        Status setup()
        void cleanup()

        void update_state(const string& state_serialized)


cdef class PyPlayer(object):
    cdef unique_ptr[Player] __player_ptr
    cdef Player* __player
    cdef str __realm
    cdef readonly object player_state_changed

    cdef Player* get(self) nogil
    cdef Player* release(self) nogil

    @staticmethod
    cdef void _state_callback(void* c_self, const string& state_serialized) with gil

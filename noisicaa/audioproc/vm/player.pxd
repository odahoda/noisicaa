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
from libcpp.string cimport string
from libcpp.functional cimport function

from noisicaa.core.status cimport *
from .host_data cimport *
from .musical_time cimport *

cdef extern from "noisicaa/audioproc/vm/player.h" namespace "noisicaa" nogil:
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
            HostData* host_data,
            void (*state_callback)(void*, const string&),
            void* userdata)

        Status setup()
        void cleanup()

        void update_state(const string& state_serialized)

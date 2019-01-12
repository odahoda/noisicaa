# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
from libcpp.string cimport string

from noisicaa.core.status cimport Status
from noisicaa.host_system cimport host_system as host_system_lib
from noisicaa.audioproc.engine cimport realm as realm_lib
from noisicaa.audioproc.engine cimport backend as backend_lib


cdef extern from "noisicaa/audioproc/engine/engine.h" namespace "noisicaa" nogil:
    cppclass Engine:
        Engine(
            host_system_lib.HostSystem* host_system,
            void (*callback)(void*, const string&),
            void* userdata)

        Status setup()
        void cleanup()

        Status setup_thread();
        void exit_loop()
        Status loop(realm_lib.Realm* realm, backend_lib.Backend* backend) nogil

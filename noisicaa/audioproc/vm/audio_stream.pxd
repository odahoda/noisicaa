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

from libcpp.string cimport string

from noisicaa.core.status cimport *

cdef extern from "noisicaa/audioproc/vm/audio_stream.h" namespace "noisicaa" nogil:
    cppclass AudioStreamBase:
        Status setup()
        void cleanup()

        string address() const

        void close()
        StatusOr[string] receive_bytes()
        Status send_bytes(const string& block_bytes)


    cppclass AudioStreamServer(AudioStreamBase):
        AudioStreamServer(const string& address);

        Status setup();
        void cleanup();


    cppclass AudioStreamClient(AudioStreamBase):
        AudioStreamClient(const string& address);

        Status setup();
        void cleanup();

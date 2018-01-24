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
from libcpp.string cimport string

from noisicaa.core.status cimport *
from .vm cimport *
from .buffers cimport *
from .block_context cimport *

cdef extern from "noisicaa/audioproc/vm/backend.h" namespace "noisicaa" nogil:
    struct BackendSettings:
        string ipc_address
        string datastream_address
        uint32_t block_size
        float time_scale

    cppclass Backend:
        @staticmethod
        StatusOr[Backend*] create(const string& name, const BackendSettings& settings)

        Status setup(VM* vm)
        void cleanup()
        Status send_message(const string& msg)
        Status set_block_size(uint32_t block_size)
        Status begin_block(BlockContext* ctxt)
        Status end_block(BlockContext* ctxt)
        Status output(BlockContext* ctxt, const string& channel, BufferPtr samples)

        void stop()
        bool stopped() const

        void release()
        bool released() const


cdef class PyBackendSettings(object):
    cdef BackendSettings __settings

    cdef BackendSettings get(self)

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

from libc.stdint cimport uint32_t, uint64_t
from libcpp.string cimport string
from libcpp.memory cimport unique_ptr

from noisicaa.core.status cimport *
from .buffers cimport *
from .block_context cimport *
from .processor_spec cimport *
from .host_data cimport *


cdef extern from "noisicaa/audioproc/vm/processor.h" namespace "noisicaa" nogil:
    cppclass Processor:
        @staticmethod
        StatusOr[Processor*] create(
            const string& node_id, HostData* host_data, const string& name)

        uint64_t id() const
        const string& node_id() const

        Status setup(const ProcessorSpec* spec)
        void cleanup()

        StatusOr[string] get_string_parameter(const string& name)
        Status set_string_parameter(const string& name, const string& value)

        StatusOr[int64_t] get_int_parameter(const string& name)
        Status set_int_parameter(const string& name, int64_t value)

        StatusOr[float] get_float_parameter(const string& name)
        Status set_float_parameter(const string& name, float value)

        Status connect_port(uint32_t port_idx, BufferPtr buf)
        Status run(BlockContext* ctxt)


cdef class PyProcessor(object):
    cdef bytes __name
    cdef PyProcessorSpec __spec
    cdef unique_ptr[Processor] __processor_ptr
    cdef Processor* __processor

    cdef Processor* ptr(self)
    cdef Processor* release(self)

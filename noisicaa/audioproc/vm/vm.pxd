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

from noisicaa.core.status cimport *
from .host_data cimport *
from .block_context cimport *
from .control_value cimport *
from .processor cimport *
from .player cimport *

cdef extern from "noisicaa/audioproc/vm/vm.h" namespace "noisicaa" nogil:
    cppclass Spec
    cppclass Backend
    cppclass Buffer

    cppclass VM:
        VM(HostData* host_data, Player* player)

        Status setup()
        void cleanup()
        Status add_processor(Processor* processor)
        Status add_control_value(ControlValue* cv)
        Status set_float_control_value(const string& name, float value)
        Status send_processor_message(uint64_t processor_id, const string& msg_serialized)
        Status set_block_size(uint32_t block_size)
        Status set_spec(const Spec* spec)
        Status process_block(Backend* backend, BlockContext* ctxt)
        Buffer* get_buffer(const string& name)
